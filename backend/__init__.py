"""Backend package for REopt runner.

Configuration:
 - Set the environment variable `REOPT_NREL_API_KEY` to provide an NREL developer
	 API key that will be forwarded to the Julia process as `NREL_DEVELOPER_API_KEY`.
	 This avoids placing secrets in user shell files and keeps the key local to the
	 backend process environment.

Example:
	export REOPT_NREL_API_KEY="your_api_key_here"

"""
