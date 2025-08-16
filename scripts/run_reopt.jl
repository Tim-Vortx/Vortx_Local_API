#!/usr/bin/env julia
# Simple wrapper to run REopt from the command line and write JSON results

import Pkg
Pkg.activate(joinpath(@__DIR__, ".."))

using REopt, JuMP

function main()
    if length(ARGS) < 3
        println("Usage: run_reopt.jl <input_json> <output_json> <solver>")
        exit(1)
    end
    input_file = ARGS[1]
    output_file = ARGS[2]
    solver = ARGS[3]

    # choose solver
    if solver == "HiGHS"
        import HiGHS
        opt = HiGHS.Optimizer
    elseif solver == "GLPK"
        import GLPK
        opt = GLPK.GLPK.Optimizer
    else
        println("Unknown solver: ", solver)
        exit(2)
    end

    using JSON3
    m = Model(opt)
    results = run_reopt(m, input_file)
    JSON3.write(output_file, results)
    println("Wrote results to ", output_file)
end

main()
