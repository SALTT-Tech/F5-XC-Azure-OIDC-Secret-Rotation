#!/usr/bin/env python3
"""Rotate an F5 XC Azure OIDC client secret."""

from __future__ import annotations

import argparse
import json
import sys
from copy import deepcopy
from typing import Any
from urllib import error, request


DEFAULT_NAMESPACE = "system"
DEFAULT_PROVIDER_NAME = "azure-oidc"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Rotate the Azure OIDC client secret for an F5 XC tenant."
    )
    parser.add_argument("--tenant", required=True, help="Tenant short name, for example 'saltt'.")
    parser.add_argument(
        "--api-token",
        required=True,
        help="F5 XC API token without the 'APIToken ' prefix.",
    )
    parser.add_argument(
        "--client-secret",
        required=True,
        help="New Azure OIDC client secret to write into the provider.",
    )
    parser.add_argument(
        "--provider-name",
        default=DEFAULT_PROVIDER_NAME,
        help=f"OIDC provider name. Default: {DEFAULT_PROVIDER_NAME}.",
    )
    parser.add_argument(
        "--namespace",
        default=DEFAULT_NAMESPACE,
        help=f"OIDC provider namespace. Default: {DEFAULT_NAMESPACE}.",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=30,
        help="HTTP timeout in seconds. Default: 30.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the update payload with the secret redacted and exit without POSTing.",
    )
    return parser.parse_args()


def build_headers(api_token: str, tenant: str) -> dict[str, str]:
    return {
        "accept": "application/json",
        "Content-Type": "application/json",
        "Access-Control-Allow-Origin": "*",
        "Authorization": f"APIToken {api_token}",
        "x-volterra-apigw-tenant": tenant,
    }


def api_url(tenant: str, namespace: str, provider_name: str) -> str:
    return (
        f"https://{tenant}.console.ves.volterra.io/api/web/custom/"
        f"namespaces/{namespace}/oidc_providers/{provider_name}"
    )


def http_json(
    method: str,
    url: str,
    headers: dict[str, str],
    timeout: int,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    req = request.Request(url=url, data=data, headers=headers, method=method)
    try:
        with request.urlopen(req, timeout=timeout) as response:
            body = response.read().decode("utf-8")
    except error.HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(
            f"{method} {url} failed with HTTP {exc.code}: {error_body}"
        ) from exc
    except error.URLError as exc:
        raise RuntimeError(f"{method} {url} failed: {exc.reason}") from exc

    try:
        return json.loads(body)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"{method} {url} returned non-JSON response: {body}") from exc


def build_update_payload(get_response: dict[str, Any], client_secret: str) -> dict[str, Any]:
    try:
        oidc_object = get_response["object"]
        metadata = oidc_object["metadata"]
        gc_spec = oidc_object["spec"]["gc_spec"]
        azure_spec = deepcopy(gc_spec["azure_oidc_spec_type"])
    except KeyError as exc:
        raise RuntimeError(f"GET response is missing expected field: {exc}") from exc

    azure_spec["client_secret"] = client_secret

    payload = {
        "name": metadata["name"],
        "namespace": metadata["namespace"],
        "spec": {
            "provider_type": gc_spec["provider_type"],
            "azure_oidc_spec_type": azure_spec,
        },
    }

    redirect_uri = gc_spec.get("redirect_uri")
    if redirect_uri:
        payload["spec"]["redirect_uri"] = redirect_uri

    scim_spec = gc_spec.get("scim_spec")
    if scim_spec is not None:
        payload["spec"]["scim_spec"] = scim_spec

    return payload


def redact_secret(payload: dict[str, Any]) -> dict[str, Any]:
    redacted = deepcopy(payload)
    try:
        redacted["spec"]["azure_oidc_spec_type"]["client_secret"] = "***REDACTED***"
    except KeyError:
        pass
    return redacted


def print_result(response: dict[str, Any], tenant: str, namespace: str, provider_name: str) -> None:
    if response == {"err": "EOK"}:
        print(
            "Secret rotation succeeded for "
            f"{tenant}/{namespace}/{provider_name}."
        )
        return

    print("Secret rotation request completed. API response:")
    json.dump(response, sys.stdout, indent=2)
    sys.stdout.write("\n")


def main() -> int:
    args = parse_args()
    url = api_url(args.tenant, args.namespace, args.provider_name)
    headers = build_headers(args.api_token, args.tenant)

    current = http_json("GET", url, headers, args.timeout)
    update_payload = build_update_payload(current, args.client_secret)

    if args.dry_run:
        json.dump(redact_secret(update_payload), sys.stdout, indent=2)
        sys.stdout.write("\n")
        return 0

    response = http_json("POST", url, headers, args.timeout, update_payload)
    print_result(response, args.tenant, args.namespace, args.provider_name)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RuntimeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(1)
