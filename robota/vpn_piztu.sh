#!/usr/bin/env bash
# Cloudflare-k GitHub-eko zerbitzarien IPak blokeatzen ditu webgune batzuetan (403).
# Haietarako trafikoa BAKARRIK etxeko VPN-tik bideratzen da (split tunnel): beste guztia
# GitHub-etik zuzenean doa, eta etxeko sarera ez da beste ezer sartzen.
#
# Secret-a (Settings → Secrets and variables → Actions):
#   WIREGUARD_KONFIG  WireGuard-en .conf fitxategiaren eduki osoa
set -euo pipefail

OSTALARIAK=(www.culturanavarra.es www.mondosonoro.com)
PROBA_URL="https://www.culturanavarra.es/es/agenda/"

if [ -z "${WIREGUARD_KONFIG:-}" ]; then
  echo "::notice::WIREGUARD_KONFIG secret-ik ez; VPNrik gabe jarraitzen da"
  exit 0
fi

# IPak orain ebatzi, GitHub-eko DNSarekin, eta /etc/hosts-en finkatu: horrela DNSak ez du
# VPNtik pasatu behar, eta bideratutako IPak eta erabiltzen direnak berdinak dira.
IPAK=()
for h in "${OSTALARIAK[@]}"; do
  ip=$(getent ahostsv4 "$h" | awk 'NR==1 {print $1}')
  [ -n "$ip" ] || { echo "::warning::Ezin izan da $h ebatzi"; continue; }
  echo "$ip $h" | sudo tee -a /etc/hosts >/dev/null
  IPAK+=("$ip")
  echo "$h → $ip (VPN bidez)"
done
[ ${#IPAK[@]} -gt 0 ] || exit 1

sudo apt-get install -y -qq wireguard-tools >/dev/null
baimenduak=$(printf '%s/32, ' "${IPAK[@]}")
# DNS lerroa kendu (GitHub-eko DNSa mantendu) eta AllowedIPs gure IPetara mugatu
printf '%s\n' "$WIREGUARD_KONFIG" \
  | sed -E '/^[[:space:]]*DNS[[:space:]]*=/d; s|^[[:space:]]*AllowedIPs[[:space:]]*=.*|AllowedIPs = '"${baimenduak%, }"'|' \
  | sudo tee /etc/wireguard/etxea.conf >/dev/null
sudo chmod 600 /etc/wireguard/etxea.conf
sudo wg-quick up etxea

kodea=$(curl -s -o /dev/null -w '%{http_code}' --max-time 20 -A "kulturaInguruan/0.1" "$PROBA_URL" || true)
if [ "$kodea" = "200" ]; then
  echo "VPN ondo: Cultura Navarra-k $kodea erantzun du"
else
  echo "::warning::VPN piztuta, baina Cultura Navarra-k $kodea erantzun du"
fi
