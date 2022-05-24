import pandas as pd
import argparse
import json
import os


def get_parser():
    """Set parameters for the experiment."""
    parser = argparse.ArgumentParser(
        "Spike detection", description="Domain Adaptation on sleep EEG."
    )
    parser.add_argument("--path_data", type=str, default="../IvadomedNifti/")

    return parser


# Experiment name
parser = get_parser()
args = parser.parse_args()

# load data filtered
path_data = args.path_data

df = pd.read_csv(os.path.join(path_data, "participants.tsv"), sep='\t')

participant_ids = df['participant_id'].to_numpy()

for participant_id in participant_ids:

    config_json_name = "config_for_training_{}.json".format(participant_id)

    os.system('ivadomed --test -c {}'.format(os.path.join(path_data, config_json_name)))
