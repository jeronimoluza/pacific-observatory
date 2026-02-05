import pandas as pd


def read_epu_files(data_dir, countries_slugs):
    epu_list = []
    for country in countries_slugs:
        epu_file = data_dir / f"{country}/epu/epu.csv"
        epu = pd.read_csv(epu_file)
        epu["date"] = pd.to_datetime(epu["date"], format="mixed")
        epu["EPU_index_ma3"] = epu["EPU_index"].rolling(window=3).mean()
        epu["country"] = country
        # Select relevant columns
        cols = ["date", "country", "EPU_index", "EPU_index_ma3"]
        # Add topic columns if present
        for topic in ["inflation", "job"]:
            topic_col = f"EPU_{topic}_index"
            if topic_col in epu.columns:
                epu[f"{topic_col}_ma3"] = epu[topic_col].rolling(window=3).mean()
                cols.extend([topic_col, f"{topic_col}_ma3"])
        epu = epu[cols]
        epu_list.append(epu)
    return pd.concat(epu_list).reset_index(drop=True)


def group_monthly(data):
    # This function should average scores like epu_weighted, epu_unweighted
    # and sum news counts per month
    data["date"] = pd.to_datetime(data["date"], format="mixed")
    data["date"] = data["date"].apply(
        lambda x: pd.to_datetime(str(x.year) + "-" + str(x.month).zfill(2) + "-01")
    )
    date_country_cols = ["date", "country"]
    sum_columns = [col for col in data.columns if "news_count" in col]
    mean_columns = [col for col in data.columns if "epu_" in col or "EPU_" in col]
    sum_data = data[date_country_cols + sum_columns].groupby(date_country_cols).sum()
    mean_data = data[date_country_cols + mean_columns].groupby(date_country_cols).mean()
    data = pd.concat([sum_data, mean_data], axis=1)
    data = data.reset_index()

    return data
