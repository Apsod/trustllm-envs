# This patching version of parallel data processing was implemented on
# top of `scripts/convert_dataset_json.py` at revision
# 1ef7409c8fa8f8a4ece7dd5935ecb02a09f6044a.

"""
Parallel streaming dataset conversion scripts for JSON files.
"""

import functools
import glob
import os

import datasets

import convert_dataset_json


def patch_load_hf_dataset(
        path: str,
        split: str,
        world_size: int,
        rank: int,
) -> None:
    old_load_hf_dataset = datasets.load_dataset

    @functools.wraps(old_load_hf_dataset)
    def new_load_hf_dataset(*args, **kwargs):
        hf_dataset = old_load_hf_dataset(*args, **kwargs)

        # Try to prevent us from messing with the dataset in unrelated
        # calls.
        if os.path.isdir(path):
            data_files = glob.glob(f'{path}/*')
        else:
            data_files = path
        if (
                args[0] == 'json'
                and kwargs['data_files'] == data_files
                and kwargs['split'] == split
        ):
            hf_dataset = hf_dataset.shard(num_shards=world_size, index=rank)

        return hf_dataset

    datasets.load_dataset = new_load_hf_dataset


if __name__ == '__main__':
    if 'WORLD_SIZE' not in os.getenv or 'RANK' not in os.getenv:
        print(
            'The `WORLD_SIZE` and `RANK` environment variables need to be '
            'defined for parallel data processing, where `WORLD_SIZE` is the '
            'number of processes, and `RANK` is the index of this process.'
        )
        exit(1)

    world_size = int(os.environ['WORLD_SIZE'])
    rank = int(os.environ['RANK'])

    args = convert_dataset_json.parse_args()

    patch_load_hf_dataset(
        path=args.path,
        split=args.split,
        world_size=world_size,
        rank=rank,
    )
    # Give each process its own output directory
    args.out_root = os.path.join(args.out_root, str(rank))

    convert_dataset_json.main(args)
