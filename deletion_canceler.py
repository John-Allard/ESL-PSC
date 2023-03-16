# a script to create a modified set of alignment files in which any gap in any
# species will trigger the replacment of that position accross all species with
# a gap.  This version is designed to deal with 2x2 matrices where all species
# have to be canceled at each gap site because canceling only one +1/-1 pair
# would leave only 1x1 which is not informative.  It can also cancel out
# tri-allelic sites which might be mostly uninformative with 2x2 species ESL
# there is also an option to impute genes from related species when missing

import os, sys, argparse, itertools, time, datetime
import esl_ct_functions as ecf 
from Bio import SeqIO
from Bio.Seq import Seq
from Bio.SeqRecord import SeqRecord

# sample run command
""" 
python3 deletion_canceler.py \
--alignments_dir '/home/john/mlpack_sg_lasso/longevity_ptp/esl_input/orthomam_alignments' \
--canceled_alignments_dir '/home/john/mlpack_sg_lasso/longevity_ptp/esl_input/orthomam_echo_alignments_canceled_gaps_new_test' \
--species_groups_file '/home/john/mlpack_sg_lasso/longevity_ptp/esl_input/orthomam_echo_species_groups_for_deletion_canceler.txt'
"""
# with response file
"""
python3 deletion_canceler.py \
--alignments_dir '/home/john/mlpack_sg_lasso/longevity_ptp/esl_input/orthomam_alignments' \
--canceled_alignments_dir '/home/john/mlpack_sg_lasso/longevity_ptp/esl_input/orthomam_bodymass_7pairs_canceled_min5' \
--response_file '/home/john/mlpack_sg_lasso/longevity_ptp/esl_input/orthomam_bodymass_response_matrix.txt' \
--cancel_only_partner \
--min_pairs 5
"""

def parse_species_groups(species_group_file_path):
    '''open a species groups file and read it and make a list of combos'''
    with open(species_group_file_path) as species_file:
        species_group_lines = species_file.readlines()
    # make a list of lists of species 
    group_list = [[species.strip() for species in group.split(',')]
                  for group in species_group_lines] # split species & strip
    list_of_species_combos = list(itertools.product(*group_list))
    print(list_of_species_combos)
    return list_of_species_combos

def get_deletion_canceler_args(parser):
    '''takes an arg parser as an argument and adds args for deletion canceler'''
    group = parser.add_argument_group('Gap-canceled Alignments Folder')
    group.add_argument('--canceled_alignments_dir',
                        help = ('Full path to the new alignments directory. '
                                'Gap-canceled alignments for each species '
                                'combo will be placed here. '
                                'This may also be an existing folder of gap-'
                                'canceled alignments for multimatrix esl.'),
                        type = str)

    # response_file and species_groups_file are mutually exclusive
    # but species_groups_file must be given for
    group = parser.add_argument_group('Deletion Canceler Options')
    group2 = group.add_mutually_exclusive_group()
    help_txt = '''full path to a response matrix file, *must be* in order:
    1, -1, 1, -1 etc.'''
    group2.add_argument('--response_file', type=str)
    
    help_txt = '''full path to a text file that contains a comma delimited list
    on each line of species that are interchangeable for each member of each
    pair the rows must be in order : 1, -1, 1, -1 etc... a seperate set of
    gap-canceled alignments will be made for each combination. This is required
    for multimatrix esl integrations with esl_multimatrix.py.
    '''
    group2.add_argument('--species_groups_file',
                       help = help_txt,
                       type=str)

    ######### Options #########
    group.add_argument('--cancel_tri_allelic',
                        help = "flag to cancel tri allelic sites",
                        action='store_true',
                        default=False)
    
    group.add_argument('--nix_full_deletions',
                        help = "don't create files for fully canceled genes",
                        action='store_true',
                        default=False)
    # flag to cancel only partner
    group.add_argument('--cancel_only_partner',
                        help = "only cancel partner of any gap species at site",
                        action='store_true',
                        default=False)
    # minimum number of uncanceled pairs to require or whole gene is excluded
    # If there are at least args.min_pairs pairs with sequence at a site,
    # then if cancel_only_partner is set, only gap cancel the partners of the
    # sequences with gaps at that site. Otherwise cancel all if theres one gap
    group.add_argument('--min_pairs',
                        help = ("num pairs that must not have gaps or whole"
                        "site will be canceled"),
                        type=int, default=2)
    # this will be a file path for a text file containing a python dict of
    #   species in the response as keys and a list of alternate species from
    #   which to impute missing sequences as the values.  It's converted from
    #   string to dict must be proper format
    group.add_argument('--impute', help = 'not fully implemented', type = str)
    group.add_argument('--limited_genes_list',
                        help = 'Use only genes in this list. One file per line',
                        type = str, default = None)
    return parser

def generate_gap_canceled_alignments(args, list_of_species_combos,
                                     enumerate_combos = False,
                                     limited_genes_list = None):
    '''cancel deletions and generate alignment files.'''

    # make the new alignments main directory if it doesn't already exist
    if not os.path.exists(args.canceled_alignments_dir):
        os.mkdir(args.canceled_alignments_dir)
    print("New alignments folder: " + args.canceled_alignments_dir)

    # if we are only using a subset of genes in the input alignments make a set
    if limited_genes_list:
        genes_to_cancel_set = set(ecf.file_lines_to_list(limited_genes_list))

    # loop through all combinations and generate alignment files
    for combo_num, species_to_scan_list in enumerate(list_of_species_combos):

        #create directory for alignments for this combination of species
        if len(list_of_species_combos) > 1: # if only 1 no need for subfolders
            if not enumerate_combos:
                new_alignments_dir = (os.path.join(args.canceled_alignments_dir,
                                                  '-'.join(species_to_scan_list)
                                                  + '-alignments'))
            else:
                new_alignments_dir = (os.path.join(args.canceled_alignments_dir,
                                                  'combo_' + str(combo_num)
                                                  + '-alignments'))
            ecf.clear_existing_folder(new_alignments_dir) # delete it if exists
            os.mkdir(new_alignments_dir)
        else: # if only 1 combo no need for subfolders
            new_alignments_dir = args.canceled_alignments_dir
                
        print('generating alignments for ' + ' '.join(species_to_scan_list))

        # get list of files to loop through
        os.chdir(args.alignments_dir)
        files_list = os.listdir()

        # change to new alignment files directory where new files will be put
        os.chdir(new_alignments_dir)

        # create a count of genes that had to be fully canceled
        fully_canceled_genes = 0

        # loop through files and check for gaps, cancel, and write new files
        file_count = 0
        for file_name in files_list:
            species_canceled = [] #keep track of species canceled (boolean list)
            file_count += 1
            if file_count % 1000 == 0:
                print('scanning file number ' + str(file_count))
            records = []
            if file_name[-3:] != 'fas':
                continue # skip if not a fasta file
            # if using a subset of the genes in the input alignments skip others
            if limited_genes_list:
                if file_name not in genes_to_cancel_set:
                    continue
            os.chdir(args.alignments_dir) #be in original files directory
            # parse fasta file and create seq dict
            record_dict = SeqIO.to_dict(SeqIO.parse(file_name, "fasta"))
            # get sequence length by taking 1st seq from dictionary values list
            sequence_length = len(list(record_dict.values())[0])

            # check if any of species to scan are missing and add them as gaps
            # or if we want to impute sequences do that too
            for species in species_to_scan_list:
                if species in record_dict:
                    # if its there add it from the record_dict
                    records.append(record_dict[species])
                    species_canceled.append(False)
                elif (args.impute and any(
                    [True for backup_species in imputation_dict[species] if
                     backup_species in record_dict])):
                    # this means at least one back up species is available so
                    # find first one and add that sequence for this species
                    for backup_species in imputation_dict[species]:
                        if backup_species in record_dict:
                            # add the sequence
                            seq_to_sub_in = record_dict[backup_species].seq
                            records.append(SeqRecord(seq_to_sub_in,
                                             id = species,
                                             description = ""))
                            break
                    species_canceled.append(False)
                else:
                    records.append(SeqRecord(Seq('-' * sequence_length),
                                         id = species,
                                         description = ""))
                    # this means the species is canceled so add a True
                    species_canceled.append(True)
            if any(species_canceled):
                if not args.cancel_only_partner:
                    fully_canceled_genes += 1
                if args.nix_full_deletions:
                    continue # don't make a file for this one if any canceled

            # check if whole gene will be fully canceled due to missing species
            # make a list of 2-item lists, one for each contrast pair
            # item for each species is a True of False of whether its missing
            if len(species_to_scan_list) % 2 == 0: #only do if even # of species
                species_pair_canc = [species_canceled[n:n+2] for n in
                                         range(0,len(species_canceled),2)]
                num_uncanceled_pairs = 0
                for species1_canceled, species2_canceled in species_pair_canc:
                    # check if either member of each pair is missing and tally
                    if not (species1_canceled or species2_canceled):
                        num_uncanceled_pairs += 1
                # check if whole gene will be canceled due to too few pairs left
                if num_uncanceled_pairs < args.min_pairs:
                    fully_canceled_genes += 1

            # ***Now do the checking and canceling   
            # make a list of the sequences which are converted from str to lists
            seq_list = [list(record.seq) for record in records]
            # loop through all positions, replace with '-' where necessary
            for index in range(len(seq_list[0])):
                # make list of AAs at this position
                position_list = [seq[index] for seq in seq_list]
                
                if args.cancel_only_partner: # will cancel if partner has a gap
                    # first check if there are enough non-gap containing pairs 
                    # there must be at least args.min_pairs
                    pair_list = [position_list[n:n+2] for n in
                                     range(0, len(position_list), 2)]
                    gap_free_pairs_count = 0
                    for pair in pair_list:
                        if '-' not in pair:
                            gap_free_pairs_count += 1
                    # check if enough pairs
                    if args.min_pairs > gap_free_pairs_count:
                        # if not enough remaining, cancel the site
                        for seq_num in range(len(seq_list)):
                            seq_list[seq_num][index] = '-'
                    else:
                        #now just cancel the partner of any gap
                        for seq_num in range(0, len(seq_list), 2): #1, 3, 5...
                            if (seq_list[seq_num][index] == '-' or
                                seq_list[seq_num + 1][index] == '-'):
                                seq_list[seq_num][index] = '-'
                                seq_list[seq_num + 1][index] = '-'
                            
                elif '-' in {seq[index] for seq in seq_list}: # set comprehen.
                    # if theres any gap, replace all AAS at position with gap 
                    for seq_num in range(len(seq_list)):
                        seq_list[seq_num][index] = '-'

                # if we want to cancel triallelic sites (only if 2 pairs)
                if args.cancel_tri_allelic and len(species_to_scan_list) == 4: 
                    # if length of set is 3, its a triallelic site so cancel it
                    if len({seq[index] for seq in seq_list}) == 3:
                        for seq_num in range(len(seq_list)):
                            seq_list[seq_num][index] = '-'


            # now write new fasta file with modified sequences
            # first modify seq_records
            for seq_num, record in enumerate(records):
                record.seq = Seq(''.join(seq_list[seq_num]))
            # change to new alignment files directory to write new file
            os.chdir(new_alignments_dir)
            # write new file
            with open(file_name, "w") as output_handle:
                SeqIO.write(records, output_handle, "fasta-2line")
                # note that ESL preprocess requires 2-line fasta alignment files

    print("number of genes fully canceled: " + str(fully_canceled_genes ))
    return


if __name__ == '__main__':
    start_time = time.time()

    # Create the parser
    parser = argparse.ArgumentParser(description = 'ESL-CT deletion canceler\n'
                                     '* indicates required arguments.') 

    # ************Add arguments************
    parser.add_argument('--alignments_dir',
                    help = '* Full path to the original alignments directory',
                    type = str, required = True)

    parser = get_deletion_canceler_args(parser)

    args = ecf.parse_args_with_config(parser) # checks for args in config file
    
    # get species lists 
    if args.response_file: 
        # get list of species from response file for one combination of species
        list_of_species_combos = [ecf.get_species_to_check(args.response_file,
                                  check_order = True)]
    elif args.species_groups_file:
        list_of_species_combos = parse_species_groups(args.species_groups_file)
    else:
        raise Exception("must enter either response file or species group list")

    # check for canceled_alignments_dir and substitute if none given
    if not args.canceled_alignments_dir:
        aligns_parent_dir = os.path.split(args.alignments_dir)[0]
        # take name from either response file or species groups file
        if args.response_file:
            dir_name = args.response_file.replace('.txt','')
        else: # must be a species groups file
            dir_name = args.species_groups_file.replace('.txt','')
        dir_name += '_gap-canceled_alignments'
        args.canceled_alignments_dir = os.path.join(aligns_parent_dir, dir_name)

    # if imputation dict has been included get it
    if args.impute:
        with open(args.impute) as imputation_dict_file:
            imputation_dict = dict(imputation_dict_file.read)

    generate_gap_canceled_alignments(args, list_of_species_combos)

    print("finished generating gap-canceled alignments!")

    ecf.report_elapsed_time(start_time) # print time taken for execution

     
                            
