features = config["features"]
scenario = config["workflow"]
name = config["name"]

rule make_umaps:
    input:
        f"outputs/{features}/{name}/profiles/{scenario}.parquet",
        f"outputs/{features}/{name}/curves/pods.parquet",
        f"outputs/{features}/{name}/curves/ccpods.parquet",
        f"outputs/{features}/{name}/curves/ldhpods.parquet",
        f"outputs/{features}/{name}/curves/mttpods.parquet",
    output:
        f"outputs/{features}/{name}/figures/umaps.pdf",
    benchmark:
        f"benchmarks/{features}/{name}/make_umaps.tsv"
    run:
        vs.umaps.make_umaps(*input, *output)