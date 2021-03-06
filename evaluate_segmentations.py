__author__ = 'gsanroma'

import argparse
import os
import csv
from shutil import rmtree, move
import sys

parser = argparse.ArgumentParser(description='Computes Dice score of estimated segmentations w.r.t. ground truth segmentations.\n'
                                             'Average per-label Dice score and average per-subject Dice score are stored in \n'
                                             'label_dice.csv and subj_dice.csv in est_dir directory, respectively')
parser.add_argument("--est_dir", type=str, nargs=1, required=True, help="Directory of estimated segmentations")
parser.add_argument("--est_suffix", type=str, nargs=1, required=True, help="Suffix of estimated segmentation files")
parser.add_argument("--gtr_dir", type=str, nargs=1, required=True, help="Directory of ground-truth segmentations")
parser.add_argument("--gtr_suffix", type=str, nargs=1, required=True, help="Suffix of ground truth segmentation files")
parser.add_argument("--per_subject_dice", action='store_true', help="keep per per subject dices")
parser.add_argument("--num_procs", type=int, nargs=1, default=[30], help="Number of concurrent processess")

args = parser.parse_args()
# args = parser.parse_args('--est_dir /home/sanromag/DATA/WMH/BIANCA/shahid_run '
#                          '--est_suffix _t95.nii.gz '
#                          '--gtr_dir /home/sanromag/DATA/WMH/RS/data_proc '
#                          '--gtr_suffix _WMHmaskbin.nii.gz '.split())

# start launcher and specify max amount of processes
from scheduler import Launcher, check_file_repeat

# Retrieve estimated files

files_list = os.listdir(args.est_dir[0])
est_files = [f for f in files_list if f.endswith(args.est_suffix[0])]
est_names = [f.split(args.est_suffix[0])[0] for f in est_files]
assert est_files, "No estimated segmentation found"

#
# Retrieve ground truth files

gtr_files = [f + args.gtr_suffix[0] for f in est_names]
# print('GTR FILES: %s' % gtr_files)
# print('FOUND: %s' % [os.path.exists(os.path.join(args.gtr_dir[0], f)) for f in gtr_files])
assert not False in [os.path.exists(os.path.join(args.gtr_dir[0], f)) for f in gtr_files], "Some ground-truth segmentations not found"

Nimg = len(est_files)

# temp directory
tmp_dir = os.path.join(args.est_dir[0], 'tmp')
if os.path.exists(tmp_dir):
    rmtree(tmp_dir)
os.makedirs(tmp_dir)

imagemath_path = os.path.join(os.environ['ANTSPATH'],'ImageMath')

launcher = Launcher(args.num_procs[0])

out_paths = []

for i_img in range(Nimg):

    est_path = os.path.join(args.est_dir[0], est_files[i_img])
    gtr_path = os.path.join(args.gtr_dir[0], gtr_files[i_img])
    out_path = os.path.join(tmp_dir, est_names[i_img])
    out_paths.append(out_path)

    cmdline = "%s 3 %s DiceAndMinDistSum %s %s" % (imagemath_path, out_path, est_path, gtr_path)

    qsub_launcher = Launcher(cmdline)

    print("Launching Dice evaluation job for labels %s" % est_names[i_img])

    launcher.add(est_names[i_img], cmdline, tmp_dir)
    launcher.run(est_names[i_img])

print "Waiting for Dice evaluation jobs to finish..."

launcher.wait()

print "Dice evaluation finished."

subj_dices = dict([])
label_dices = dict([])

for i, out_path in enumerate(out_paths):

    # Read per-label Dice
    check_file_repeat(out_path + '.csv')
    f = open(out_path + '.csv', 'r')
    reader = csv.reader(f)
    count = 0
    dice = 0.
    for row in reader:
        count += 1
        if count == 1: # skip header
            continue
        dice += float(row[1])
        try:
            label_dices[row[0].split('_')[1]] += float(row[1]) / len(out_paths)
        except:
            label_dices[row[0].split('_')[1]] = float(row[1]) / len(out_paths)

    f.close()

    if args.per_subject_dice:
        dice_name = est_files[i].split(os.extsep, 1)[0] + '.csv'
        move(out_path + '.csv', os.path.join(args.est_dir[0], dice_name))

    subj_dices[os.path.basename(out_path)] = dice/(count-1)


subj_dice_file = "subj_dice.csv"
label_dice_file = "label_dice.csv"

with open(os.path.join(args.est_dir[0], subj_dice_file), 'w') as csvfile:
    writer = csv.DictWriter(csvfile, subj_dices.keys())
    writer.writeheader()
    writer.writerow(subj_dices)

with open(os.path.join(args.est_dir[0], label_dice_file), 'w') as csvfile:
    writer = csv.DictWriter(csvfile, label_dices.keys())
    writer.writeheader()
    writer.writerow(label_dices)

rmtree(tmp_dir)

