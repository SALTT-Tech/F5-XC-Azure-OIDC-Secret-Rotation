# F5-XC Azure OIDC Secret Rotation

Rotate the client secret stored in an F5 Distributed Cloud (XC) Azure OIDC provider.

## Requirements

- Python 3.9 or later
- An F5 XC API token with permission to read and update OIDC providers
- F5 XC tenant short name
- The new Azure OIDC client secret
- Network access from the machine running the script to `https://<tenant>.console.ves.volterra.io`

## Usage

Run the script directly:

```bash
python3 rotate_f5_xc_azure_oidc_secret.py \
  --tenant <tenant> \
  --api-token <xc-api-token> \
  --client-secret <new-azure-client-secret>
```

### Required arguments

- `--tenant`: XC tenant short name, for example `saltt`
- `--api-token`: XC API token without the `APIToken ` prefix
- `--client-secret`: new Azure OIDC client secret to write into the provider

### Optional arguments

- `--provider-name`: OIDC provider name. Default: `azure-oidc`
- `--namespace`: OIDC provider namespace. Default: `system`
- `--timeout`: HTTP timeout in seconds. Default: `30`
- `--dry-run`: print the generated update payload with the secret redacted and exit without sending the update

### Built-in help

```bash
python3 rotate_f5_xc_azure_oidc_secret.py --help
```

## Examples

### Rotate the default provider

```bash
python3 rotate_f5_xc_azure_oidc_secret.py \
  --tenant saltt \
  --api-token "$XC_API_TOKEN" \
  --client-secret "$AZURE_CLIENT_SECRET"
```

This targets:

- Namespace: `system`
- Provider name: `azure-oidc`

### Rotate a non-default provider

```bash
python3 rotate_f5_xc_azure_oidc_secret.py \
  --tenant saltt \
  --api-token "$XC_API_TOKEN" \
  --client-secret "$AZURE_CLIENT_SECRET" \
  --namespace shared-config \
  --provider-name azure-oidc-prod
```

### Validate the outgoing payload without updating XC

```bash
python3 rotate_f5_xc_azure_oidc_secret.py \
  --tenant saltt \
  --api-token "$XC_API_TOKEN" \
  --client-secret "$AZURE_CLIENT_SECRET" \
  --dry-run
```

`--dry-run` prints the final payload with the secret replaced by `***REDACTED***`. This is useful to verify:

- the target provider exists
- the script can authenticate successfully
- the payload shape matches the current XC object

## Expected Output

Successful update:

```text
Secret rotation succeeded for <tenant>/<namespace>/<provider-name>.
```

## Failure Modes

The script exits with status code `1` and prints an error message when:

- the XC API returns an HTTP error
- the request cannot be sent because of a network or DNS issue
- the API returns non-JSON content
- the `GET` response does not contain the expected OIDC object structure

Common causes:

- wrong tenant short name
- invalid or expired API token
- insufficient XC permissions
- wrong namespace or provider name
- target provider is not an Azure OIDC provider object shaped as expected

## Security Notes

- Do not include the `APIToken ` prefix in `--api-token`; the script adds it automatically.
- Prefer passing secrets through environment variables or a secure secret store instead of placing them directly in shell history.
- `--dry-run` redacts the secret before printing output.
- A normal update run does not print the secret value.

Example using environment variables:

```bash
export XC_API_TOKEN='<xc-api-token>'
export AZURE_CLIENT_SECRET='<new-azure-client-secret>'

python3 rotate_f5_xc_azure_oidc_secret.py \
  --tenant saltt \
  --api-token "$XC_API_TOKEN" \
  --client-secret "$AZURE_CLIENT_SECRET"
```

## Operational Notes

- The script preserves existing `redirect_uri` and `scim_spec` fields if they are present in the current XC object.
- The script assumes the current provider object contains `spec.gc_spec.azure_oidc_spec_type`.
- The script does not create a provider. The target provider must already exist.
- The script performs one read and one write against the XC API for each execution.
