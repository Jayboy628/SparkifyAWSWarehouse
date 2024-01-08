import configparser
import psycopg2
import logging
import boto3  # Import boto3
import time  # Import time
from sql_queries import create_table_queries, drop_table_queries

# Configure logging
logging.basicConfig(format='%(asctime)s: %(levelname)s: %(message)s', level=logging.INFO)


def drop_tables(cur, conn):
    """Drop any existing tables from sparkifydb."""
    for query in drop_table_queries:
        try:
            cur.execute(query)
            conn.commit()
        except psycopg2.Error as e:
            logging.error(f"Error: Issue dropping table. SQL: {query}, Error: {e}")
            conn.rollback()

    logging.info("Tables dropped successfully.")


def create_tables(cur, conn):
    """Create new tables to sparkifydb."""
    for query in create_table_queries:
        try:
            cur.execute(query)
            conn.commit()
        except psycopg2.Error as e:
            logging.error(f"Error: Issue creating table. SQL: {query}, Error: {e}")
            conn.rollback()

    logging.info("Tables created successfully.")

def get_redshift_cluster_details(cluster_identifier):
    """Retrieve Redshift cluster details such as endpoint and role ARN."""
    redshift = boto3.client('redshift', region_name='us-east-1')  # replace with your region

    while True:
        try:
            cluster_props = redshift.describe_clusters(ClusterIdentifier=cluster_identifier)['Clusters'][0]
            status = cluster_props['ClusterStatus']
            logging.info(f"Cluster Status: {status}")

            if status == 'available':
                endpoint = cluster_props.get('Endpoint', {}).get('Address', None)
                role_arn = cluster_props.get('IamRoles', [{}])[0].get('IamRoleArn', None)
                return endpoint, role_arn
            else:
                logging.info("Cluster is not available yet. Waiting...")
                time.sleep(60)  # wait for 60 seconds before retrying
        except Exception as e:
            logging.error(f"Error retrieving Redshift cluster details: {e}")
            break

    return None, None  # Return Non
    
def main():
    """Main entry point of the script."""
    config = configparser.ConfigParser()
    config.read('dwh.cfg')
    conn = None  # Initialize conn here to ensure it's in the proper scope

    try:
        # Dynamically retrieve the Redshift cluster details
        DWH_CLUSTER_IDENTIFIER = config.get("CLUSTER", "CLUSTER_IDENTIFIER")
        DWH_ENDPOINT, DWH_ROLE_ARN = get_redshift_cluster_details(DWH_CLUSTER_IDENTIFIER)

        # Construct the connection string using the dynamically retrieved endpoint
        conn_string = "host={} dbname={} user={} password={} port={}".format(
            DWH_ENDPOINT,  # Use the dynamically retrieved endpoint
            config.get('CLUSTER', 'DB_NAME'),
            config.get('CLUSTER', 'USERNAME'),
            config.get('CLUSTER', 'PASSWORD'),
            config.get('CLUSTER', 'PORT')
        )

        # Print the connection string to verify it's correct
        print("Connection string:", conn_string)

        # Establish connection to the database
        conn = psycopg2.connect(conn_string)
        cur = conn.cursor()

        drop_tables(cur, conn)
        create_tables(cur, conn)

        cur.close()
    except Exception as e:
        logging.error(f"Error connecting to the database: {e}")
    finally:
        # Close the connection if it was successfully opened
        if conn:
            conn.close()
            logging.info("Database connection closed.")

if __name__ == "__main__":
    main()