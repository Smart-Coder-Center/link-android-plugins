# Native runtime signing key setup

The universal plugin publisher supports a separate signed `native_runtime` ZIP type. Do not generate or commit the private signing key.

1. Generate an Ed25519 key pair on a trusted offline workstation:

   ```sh
   openssl genpkey -algorithm ED25519 -out runtime-signing-private.pem
   openssl pkey -in runtime-signing-private.pem -pubout -out native-runtime-ed25519-public.pem
   ```

2. Add the public key as `keys/native-runtime-ed25519-public.pem` in this repository.
3. Add the complete PEM contents of `runtime-signing-private.pem` as the GitHub Actions secret named `LINK_PLUGIN_RUNTIME_SIGNING_PRIVATE_KEY`.
4. Pin the exact same public key in the signed Link Android APK. The downloaded ZIP is never a trust source for its own public key.
5. Keep the private key offline and backed up securely. Rotate it only with a coordinated app release that pins the replacement public key.

The publisher fails closed if either the repository public key or Actions secret is missing or if the key pair does not match.

**Do not publish or activate native runtime packages until the Android installer verifies the Ed25519 signature and payload hashes before extraction/loading, validates ABI and ELF metadata, uses app-private storage, and disables remote executable-code packages in Google Play builds.**
