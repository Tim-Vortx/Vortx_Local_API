# Streamlit Component Guidelines

When creating or modifying Streamlit components, ensure user input values
persist across reruns by sourcing default values from
`st.session_state`.

```python
st.number_input(
    "Discount Rate (%)",
    min_value=0.0,
    value=st.session_state.get("discount_rate_pct", 6.0),
    key="discount_rate_pct",
)
```

Always reference `st.session_state.get()` for a widget's `value` (or
`index` for widgets such as `st.radio`) and pass the same key so that the
selection is stored and restored on rerun. This consistent pattern helps
prevent regressions in state handling across the application.

