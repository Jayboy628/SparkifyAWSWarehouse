import configparser
import psycopg2
from sql_queries import copy_table_queries, insert_table_queries
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s: %(levelname)s: %(message)s')


def check_load_errors(cur):
    """Check for errors in the recent load operations."""
    cur.execute("SELECT * FROM stl_load_errors ORDER BY starttime DESC LIMIT 10;")
    errors = cur.fetchall()
    if errors:
        logging.error("Errors detected in load operations:")
        for error in errors:
            logging.error(error)

def check_load_commits(cur):
    """Check for errors in the recent load operations."""
    cur.execute("SELECT * FROM stl_load_commits WHERE filename LIKE '%log_data%';")
    errors = cur.fetchall()
    if errors:
        logging.error("Errors detected in load operations:")
        for error in errors:
            logging.error(error)

def load_staging_tables(cur, conn):
    """Load data from S3 to staging tables in Redshift."""
    logging.info("Starting to load data from S3 to staging tables...")
    for i, query in enumerate(copy_table_queries, 1):
        try:
            logging.info(f"Loading table {i}/{len(copy_table_queries)}: {query}")
            cur.execute(query)
            conn.commit()
        except psycopg2.Error as e:
            logging.error(f"Error loading table {i}: {e}")
            conn.rollback()  # rollback the transaction on error
    logging.info("Completed loading data into staging tables.")

def insert_into_tables(cur, conn):
    """Insert data from staging tables into analytics tables."""
    logging.info("Starting to insert data from staging tables into analytics tables...")
    for i, query in enumerate(insert_table_queries, 1):
        try:
            logging.info(f"Inserting data {i}/{len(insert_table_queries)}: {query}")
            cur.execute(query)
            conn.commit()
        except psycopg2.Error as e:
            logging.error(f"Error inserting data {i}: {e}")
            conn.rollback()  # rollback the transaction on error
    logging.info("Completed inserting data into analytics tables.")

def main():
    """Connect to Redshift, load staging tables, and insert into analytics tables."""
    config = configparser.ConfigParser()
    config.read('dwh.cfg')

    # Extract and print credentials for verification
    host = config.get('CLUSTER', 'DWH_ENDPOINT')
    dbname = config.get('CLUSTER', 'DB_NAME')
    user = config.get('CLUSTER', 'USERNAME')
    password = config.get('CLUSTER', 'PASSWORD')
    port = config.get('CLUSTER', 'PORT')

    # Validate the port
    if not port.isdigit() or not 1 <= int(port) <= 65535:
        logging.error(f"Error: Port '{port}' is not a valid integer within the TCP port range.")
        return  # Exit if the port is not valid

    conn = None
    try:
        conn = psycopg2.connect(f"host={host} dbname={dbname} user={user} password={password} port={port}")
        cur = conn.cursor()
        logging.info("Connected to the Redshift cluster.")

        load_staging_tables(cur, conn)
        insert_into_tables(cur, conn)

        logging.info("ETL process completed successfully.")

    except psycopg2.DatabaseError as db_err:
        logging.error("Database connection failed.")
    except configparser.Error as cfg_err:
        logging.error(f"Configuration error: {cfg_err}")
    except Exception as e:
        logging.error(f"Unexpected error: {e}")
    finally:
        if conn:
            cur.close()
            conn.close()
            logging.info("Redshift connection closed.")

if __name__ == "__main__":
    main()
