#!/usr/bin/env python
import argparse
import os
import sys
from datetime import date

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from generators.generator_helpers import (process_master_log,
                                          validate_summary_table,
                                          integrate_brokerage_data,
                                          write_db,
                                          get_brokerage_data_from_csv)
from libraries.pandas_helpers import print_full
from libraries.helpers import build_master_log

def process_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Generate and validate summary table')
    parser.add_argument('brokerage_data_file', type=str, nargs='?',
                        help='Brokerage data file to process (csv); not required for --export-csv')

    action_group = parser.add_mutually_exclusive_group(required=True)
    action_group.add_argument('--validate-only', action='store_true',
                              help="Only validate summary table and exit")
    action_group.add_argument('--write-db', action='store_true', default=False,
                              help="Write summary table to database")
    action_group.add_argument('--export-csv', action='store_true', default=False,
                              help="Export current portfolio summary from DB to CSV")

    parser.add_argument('--silent', action='store_true', default=False,
                        help="Do not print sql statements")
    parser.add_argument('--output', type=str, default=None,
                        help="Output file path for --export-csv (default: portfolio_summary_YYYYMMDD.csv)")
    return parser.parse_args()


def run_export_csv(output_file: str) -> None:
    """Query DB for current holdings and write to CSV."""
    import pandas as pd
    from libraries.db.mysqldb import MysqlDB
    from libraries.db.dbcfg import dbcfg

    sql = """
        SELECT entities.name, entities.symbol, entities.asset_type, entities.sector,
               summary.current_shares, summary.cost_basis, summary.first_purchase_date,
               summary.last_purchase_date, summary.account_type, summary.dividend_yield,
               summary.total_dividend
        FROM entities
        LEFT JOIN summary ON entities.symbol = summary.symbol
        WHERE current_shares > 0
        ORDER BY symbol
    """

    with MysqlDB(dbcfg) as db:
        db.execute(sql)
        columns = [desc[0] for desc in db.cursor.description]
        rows = db.fetchall()

    df = pd.DataFrame(rows, columns=columns)
    df.to_csv(output_file, index=False)
    print(f"Exported {len(df)} rows to {output_file}")


def main():
    args = process_args()

    if args.export_csv:
        output_file = args.output or f"portfolio_summary_{date.today().strftime('%Y%m%d')}.csv"
        run_export_csv(output_file)
        return

    if not args.brokerage_data_file:
        print("error: brokerage_data_file is required for --validate-only and --write-db")
        sys.exit(1)

    master_log_df = build_master_log()

    summary_df = process_master_log(master_log_df)

    brokerage_df = get_brokerage_data_from_csv(args.brokerage_data_file)

    errors = validate_summary_table(summary_df, brokerage_df)

    summary_df = integrate_brokerage_data(summary_df, brokerage_df)

    # Sort summary_df by symbol
    summary_df = summary_df.sort_values(by=['Symbol'], ignore_index=True)

    print_full(summary_df)
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