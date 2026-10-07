from google.cloud import bigquery


def test_bigquery_connection() -> None:
    client = bigquery.Client()

    datasets = list(client.list_datasets())

    print(f"Connected project: {client.project}")
    print(f"Datasets visible: {len(datasets)}")

    for dataset in datasets:
        print(f"- {dataset.dataset_id}")

    assert client.project