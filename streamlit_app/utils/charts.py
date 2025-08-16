import altair as alt
import pandas as pd

def daily_ops_chart(df: pd.DataFrame):
    stack_keys = ["Utility","Solar → Load","BESS → Load","Diesel → Load","NG (CHP) → Load"]

    stacked = df.melt(id_vars=["hour","load"], value_vars=stack_keys, var_name="Source", value_name="kW")
    area = alt.Chart(stacked).mark_area().encode(
        x=alt.X("hour:Q", title="Hour"),
        y=alt.Y("kW:Q", stack="zero", title="kW"),
        color=alt.Color("Source:N", legend=alt.Legend(orient="bottom")),
        tooltip=["Source","kW"]
    )
    load_line = alt.Chart(df).mark_line().encode(
        x="hour:Q", y=alt.Y("load:Q", title="kW"), tooltip=["hour","load"]
    )
    return (area + load_line).resolve_scale(y="independent").properties(height=320)

def monthly_perf_chart(monthly_df: pd.DataFrame):
    mdf = monthly_df.melt(id_vars=["Month"], var_name="Metric", value_name="MWh")
    return alt.Chart(mdf).mark_bar().encode(
        x=alt.X("Month:N", sort=list(monthly_df["Month"])),
        y=alt.Y("MWh:Q"),
        color="Metric:N",
        tooltip=["Month","Metric","MWh"]
    ).properties(height=320)
