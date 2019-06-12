'''
    tactac - database for taxonomic ID and accession number resolution

    Manual under https://github.com/mariehoffmann/tactac/wiki

    author: Marie Hoffmann ozymandiaz147[at]gmail[.]com
'''

import csv
import os
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
import sys
import urllib.request

import config as cfg

'''
    Produce two files representing a taxonomic subset of the library, namely
    a taxonomy file in csv format [taxid, p_taxid], list of accessions for each taxid
    in the format [taxid,acc1, acc2,...], and a fasta file with sequences
    corresponding to the collected accessions constituting the taxonomic subtree
    as a subset of the 'nt' dataset.
'''
def subtree(args):
    taxid = int(args.subtree[0])
    if not os.path.exists(cfg.DIR_SUBSET):
        os.makedirs(cfg.DIR_SUBSET)
    dir_subset_tax = os.path.join(cfg.DIR_SUBSET, str(taxid))
    if not os.path.exists(dir_subset_tax):
        os.mkdir(dir_subset_tax)
    # taxonomy as tuples [taxid, parent_taxid]
    file_tax = os.path.join(dir_subset_tax, 'root_{}.tax'.format(taxid))
    # accessions as [taxid,acc1,acc2,...]
    file_acc = os.path.join(dir_subset_tax, 'root_{}.acc'.format(taxid))
    # map of positional counter (ID) and written out accession
    file_ID2acc = os.path.join(dir_subset_tax, 'root_{}.id'.format(taxid))

    # open DB connection
    con = psycopg2.connect(dbname='taxonomy', user=cfg.user_name, host='localhost', password=args.password[0])
    con.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    cur = con.cursor()

    # get tree and its assigned accession IDs
    taxid_stack = [taxid]
    accs_set = set()

    with open(file_tax, 'w') as ft, open(file_acc, 'w') as fa:
        ft.write('#taxid,parent_taxid\n')
        fa.write('#taxid,acc1,acc2,...\n')
        while len(taxid_stack) > 0:
            current_taxid = taxid_stack.pop()
            # grep all accession for current taxid
            cur.execute("SELECT accession FROM accessions WHERE tax_id = {};".format(current_taxid))
            con.commit()
            taxid2accs = str(current_taxid)
            for record in cur:
                taxid2accs += ',' + record[0]
                accs_set.add(record[0])
            # write only taxids with directly assigned accessions
            if taxid2accs.find(',') > -1:
                fa.write(taxid2accs + '\n')

            # push back taxonomic children
            cur.execute("SELECT tax_id FROM node WHERE parent_tax_id = {};".format(current_taxid))
            con.commit()
            for record in cur:
                taxid_stack.append(record[0])
                #print(record)
                ft.write('{},{}\n'.format(record[0], current_taxid))
    cur.close()
    con.close()

    print("Taxonomic subtree written to ", file_tax)
    print("Taxonomic mapping written to ", file_acc)

    # TODO: parse library and fetch all sequences given their accessions
    file_lib = os.path.join(dir_subset_tax, 'root_{}.fasta'.format(taxid))
    buffer = ''
    acc = ''
    with open(cfg.FILE_REF, 'r') as f, open(file_lib, 'w') as fw, open(file_ID2acc, 'w') as fID:
        ignore = False
        ID = 1
        for line in f:
            # new header line, check ignore flag
            if line.startswith(cfg.HEADER_PREFIX):
                mobj = cfg.RX_ACC.search(line)
                if mobj is None:
                    print('Error: could not extract accession from ', line)
                # del previously handled accession from dictionary
                if acc in accs_set:
                    accs_set.remove(acc)
                if len(accs_set) == 0:
                    break
                acc = mobj.group(1)
                if acc in accs_set:
                    ignore = False
                    fID.write("{},{}\n".format(ID, acc))
                    ID += 1
                else:
                    ignore = True
            if not ignore:
                fw.write(line)

    print("Library sequences of subtree written to ", file_lib)
    print("Position IDs of accessions written to ", file_ID2acc)