"""Utility functions to submit and poll the NREL REopt API.

This module is adapted from NREL's `google_colab_simple_examples.ipynb`
worksheet. It mirrors the `get_api_results` helper used in that notebook
so that our application can submit a scenario and poll for results using
the same logic.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict

import requests

# Default API URL for the REopt "stable" endpoint
DEFAULT_API_URL = "https://developer.nrel.gov/api/reopt/stable"


def _poll_results(url: str, poll_interval: int = 5, headers: Dict[str, str] | None = None) -> Dict[str, Any]:
    """Poll the REopt results endpoint until a terminal status is returned.

    Parameters
    ----------
    url : str
        Fully-qualified URL to the ``/results`` endpoint including the
        ``run_uuid``.
    poll_interval : int, optional
        Seconds to wait between polling attempts, by default 5.

    Returns
    -------
    Dict[str, Any]
        Parsed JSON response from the REopt API once the status is no longer
        ``"Optimizing..."``.
    """

    status = "Optimizing..."
    while status == "Optimizing...":
        resp = requests.get(url, headers=headers, verify=False)
        resp.raise_for_status()
        data = resp.json()
        # v3 places the status at the top level
        status = data.get("status") or data.get("outputs", {}).get("Scenario", {}).get("status")
        if status == "Optimizing...":
            time.sleep(poll_interval)
    return data


def _inputs_match(sent: Dict[str, Any], received: Dict[str, Any]) -> bool:
    """Recursively verify that all keys/values in ``sent`` exist in ``received``."""

    for key, value in sent.items():
        if key not in received:
            return False
        if isinstance(value, dict):
            if not isinstance(received[key], dict):
                return False
            if not _inputs_match(value, received[key]):
                return False
        else:
            if received[key] != value:
                return False
    return True


def get_api_results(
    post: Dict[str, Any],
    api_key: str,
    api_url: str = DEFAULT_API_URL,
    poll_interval: int = 5,
) -> Dict[str, Any]:
    """POST a scenario to REopt and poll for the final results.

    Parameters
    ----------
    post : dict
        Scenario inputs to send to the API.
    api_key : str
        NREL developer API key.
    api_url : str, optional
        Base URL of the REopt API, defaults to the stable endpoint.
    poll_interval : int, optional
        Seconds to wait between polling attempts, by default 5.

    Returns
    -------
    Dict[str, Any]
        Complete API response including inputs and outputs.

    Notes
    -----
    An extra boolean field ``inputs_match`` is included in the returned
    dictionary indicating whether the inputs echoed by the API contain all
    of the values that were originally sent.
    """

    post_url = f"{api_url}/job/"
    headers = {"X-Api-Key": api_key}
    resp = requests.post(post_url, json=post, headers=headers, verify=False)
    resp.raise_for_status()
    run_uuid = resp.json()["run_uuid"]

    results_url = f"{api_url}/job/{run_uuid}/results/"
    results = _poll_results(results_url, poll_interval=poll_interval, headers=headers)

    sent_inputs = post
    received_inputs = results.get("inputs", {})
    results["inputs_match"] = _inputs_match(sent_inputs, received_inputs)
    return results
