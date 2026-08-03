wildcard_constraints:
    pipeline=r"[_a-zA-Z.~0-9\-]*"

features = config["features"]
scenario = config["workflow"]
name = config["name"]

rule mad_normalize:
    input:
        f"outputs/{features}/{name}/profiles/variant_feats.parquet",
        f"outputs/{features}/{name}/profiles/neg_stats.parquet",
    output:
        f"outputs/{features}/{name}/profiles/mad.parquet",
    benchmark:
        f"benchmarks/{features}/{name}/mad_normalize.tsv"
    run:
        pp.normalize.mad(*input, *output)


rule int:
    input:
        f"outputs/{features}/{name}/profiles/{{pipeline}}.parquet",
    output:
        f"outputs/{features}/{name}/profiles/{{pipeline}}_int.parquet",
    benchmark:
        f"benchmarks/{features}/{name}/int_{{pipeline}}.tsv"
    run:
        pp.transform.rank_int(*input, *output)


rule featselect:
    input:
        f"outputs/{features}/{name}/profiles/{{pipeline}}.parquet",
    output:
        f"outputs/{features}/{name}/profiles/{{pipeline}}_featselect.parquet",
    params:
        outlier_thresh=config["outlier_feat_thresh"],
    benchmark:
        f"benchmarks/{features}/{name}/featselect_{{pipeline}}.tsv"
    run:
        pp.select_features(*input, params.outlier_thresh, *output)