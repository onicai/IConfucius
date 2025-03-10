"""Helper function to run llama.cpp from the command line using subprocess"""

import subprocess


def run_llama_cpp(
    llama_cli_path,
    model,
    prompt,
    num_tokens,
    seed,
    temp,
    # top_k,
    # top_p,
    # min_p,
    # tfs,
    # typical,
    # mirostat,
    # mirostat_lr,
    # mirostat_ent,
    repeat_penalty,
    cache_type_k,
    # cache_type_v,
    # defrag_thold,
):

    command = [
        llama_cli_path,
        "-m",
        model,
        "--no-warmup",  # needed when running from CLI. Is default for llama_cpp_canister
        "-no-cnv",  # needed when running from CLI. Is default for llama_cpp_canister
        # "--simple-io",
        # "--no-display-prompt",  # only return the generated text, without special characters
        "-sp",  # output special tokens
        "-n",
        f"{num_tokens}",
        "--seed",
        f"{seed}",
        "--temp",
        f"{temp}",
        # "--top-k",
        # f"{top_k}",
        # "--top-p",
        # f"{top_p}",
        # "--min-p",
        # f"{min_p}",
        # "--tfs",
        # f"{tfs}",
        # "--typical",
        # f"{typical}",
        # "--mirostat",
        # f"{mirostat}",
        # "--mirostat-lr",
        # f"{mirostat_lr}",
        # "--mirostat-ent",
        # f"{mirostat_ent}",
        "--repeat-penalty",
        f"{repeat_penalty}",
        "--cache-type-k",
        f"{cache_type_k}",
        # "--cache-type-v", # CPU only
        # f"{cache_type_v}",
        # "--defrag-thold", # No impact
        # f"{defrag_thold}",
        "-p",
        prompt,
    ]

    # Print the command on a single line for terminal use, preserving \n
    print(
        "\nCommand:\n",
        f"{llama_cli_path} -m {model} --no-warmup -no-cnv -sp -n {num_tokens} --seed {seed} --temp {temp} --repeat-penalty {repeat_penalty} --cache-type-k {cache_type_k} -p '{prompt}'".replace(
            "\n", "\\n"
        ),
    )

    subprocess.run(command, text=True)
