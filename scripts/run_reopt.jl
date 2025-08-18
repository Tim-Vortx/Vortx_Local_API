#!/usr/bin/env julia
# Simple wrapper to run REopt from the command line and write JSON results


import Pkg
# disable automatic package precompilation to avoid GeoInterfaceRecipes method overwrite errors
ENV["JULIA_PKG_PRECOMPILE_AUTO"] = "0"
Pkg.activate(joinpath(@__DIR__, ".."))
Pkg.add("GeoInterfaceRecipes")

using REopt, JuMP
import HiGHS
import GLPK
using JSON3

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
        opt = HiGHS.Optimizer
    elseif solver == "GLPK"
        opt = GLPK.GLPK.Optimizer
    else
        println("Unknown solver: ", solver)
        exit(2)
    end

    m = Model(opt)
    results = run_reopt(m, input_file)
    JSON3.write(output_file, results)
    println("Wrote results to ", output_file)
end

main()
