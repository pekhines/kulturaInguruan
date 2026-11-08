#!/usr/bin/env bash
# Komando bat etxeko VPN-aren namespace-an exekutatu (ikus vpn_piztu.sh), erabiltzaile berarekin
# eta ingurune-aldagai berekin (OPENROUTER_API_KEY, GITHUB_OUTPUT, PATH…).
# VPN-a piztu ez bada, zuzenean exekutatzen da, abisu batekin.
#   bash robota/vpn_bidez.sh python robota/bildu.py
set -euo pipefail

NS=etxea
if ip netns list 2>/dev/null | grep -qw "$NS"; then
  exec sudo -E ip netns exec "$NS" sudo -E -u "$(id -un)" env "PATH=$PATH" "$@"
else
  echo "::warning::VPN-a ez dago piztuta: eskaerak GitHub-etik zuzenean"
  exec "$@"
fi
