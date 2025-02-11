#!/usr/bin/env python
import argparse
import os
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from generators.generator_helpers import (process_master_log,
                                          validate_summary_table,
                                          integrate_brokerage_data,
                                          write_db,
                                          get_brokerage_data_from_csv)
from libraries.pandas_helpers import print_full
from libraries.helpers import build_master_log

def process_args() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description='Generate and validate summary table')
    parser.add_argument('brokerage_data_file', type=str, 
                        help='Brokerage data file to process (csv)')
    
    action_group = parser.add_mutually_exclusive_group(required=True)
    action_group.add_argument('--validate-only', action='store_true',
                              help="Only validate summary table and exit")
    action_group.add_argument('--write-db', action='store_true', default=False, 
                              help="Write summary table to database")

    parser.add_argument('--silent', action='store_true', default=False,
                        help="Do not print sql statements")
    return parser.parse_args()
  
def main():
    args = process_args()
    
    master_log_df = build_master_log()
    
    summary_df = process_master_log(master_log_df)

    brokerage_df = get_brokerage_data_from_csv(args.brokerage_data_file)

    errors = validate_summary_table(summary_df, brokerage_df)
    
    summary_df = integrate_brokerage_data(summary_df, brokerage_df)

    # Sort summary_df by symbol
    summary_df = summary_df.sort_values(by=['Symbol'], ignore_index=True)
    
    print()
    print()
    
    if len(errors) > 0:
        print()
        print("Errors found:")
        print()
        for error_type, error_list in errors.items():
            print("{}".format(error_type.upper()))
            for count, error in enumerate(error_list):
                print("\t{}. {}".format(count+1, error))
            print()
    else:
        print()
        print("No Errors Found!")
        print()
    
    if args.write_db:
        print("\tProposed summary table and any potential errors are shown above. "
              "Would you like to write this to the database?")
        resp = \
            input("\tEnter 'y' to write to database, anything else to exit: ")
        
        print()
        if resp.lower() == 'y':
            write_db(summary_df, not args.silent)
        else: 
            exit(0)
    
if __name__ == "__main__":
    main()