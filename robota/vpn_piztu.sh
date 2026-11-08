#!/usr/bin/env bash
# Robotaren eskaera GUZTIAK etxeko VPN-tik (webgune askok GitHub-eko IPak blokeatzen edo mugatzen
# dituzte: Cloudflare 403, pamplona.es 502…).
#
# Nola: "etxea" sare-namespace bat sortzen da, bere irteera bakarra WireGuard tunela duena.
# Robota namespace horretan exekutatzen da (ikus vpn_bidez.sh). Runner-aren gainerako trafikoa
# (git push, GitHub-eko zerbitzuak) zuzenean doa: VPN-ak huts eginda ere, datuak gordetzen dira.
# WireGuard-en UDP socketa sortu den namespace-an geratzen da (nagusian), beraz tunela bera
# internet arruntetik doa eta namespace-ko trafiko guztia haren barrutik.
#
# Secret-a (Settings → Secrets and variables → Actions):
#   WIREGUARD_KONFIG  WireGuard-en .conf fitxategiaren eduki osoa
set -euo pipefail

NS=etxea
PROBA_URL="https://www.culturanavarra.es/es/agenda/"  # GitHub-etik 403; etxetik 200

if [ -z "${WIREGUARD_KONFIG:-}" ]; then
  echo "::notice::WIREGUARD_KONFIG secret-ik ez; VPNrik gabe jarraitzen da"
  exit 0
fi

sudo apt-get install -y -qq wireguard-tools >/dev/null

# AllowedIPs = 0.0.0.0/0 (dena tuneletik) eta wg-quick-en eremuak (Address, DNS…) kendu
# (wg-quick-ek "<izena>.conf" izena eskatzen du)
karpeta=$(mktemp -d)
konf="$karpeta/etxea.conf"
printf '%s\n' "$WIREGUARD_KONFIG" \
  | sed -E 's|^[[:space:]]*AllowedIPs[[:space:]]*=.*|AllowedIPs = 0.0.0.0/0|' > "$konf"
helbideak=$(sed -nE 's/^[[:space:]]*Address[[:space:]]*=[[:space:]]*//p' "$konf" | tr ',' '\n' \
  | tr -d ' ' | grep -E '^[0-9.]+(/[0-9]+)?$' || true)
[ -n "$helbideak" ] || { echo "::error::WireGuard konfigurazioan ez dago IPv4 Address-ik"; exit 1; }
garbia="$karpeta/garbia.conf"
sudo wg-quick strip "$konf" > "$garbia"

# Interfazea namespace nagusian sortu eta konfiguratu (Endpoint-a hemen ebazten da), gero mugitu
sudo ip netns add "$NS"
sudo ip link add wg-etxea type wireguard
sudo wg setconf wg-etxea "$garbia"
rm -rf "$karpeta"
sudo ip link set wg-etxea netns "$NS"
for h in $helbideak; do
  sudo ip -n "$NS" addr add "$h" dev wg-etxea
done
sudo ip -n "$NS" link set lo up
sudo ip -n "$NS" link set wg-etxea mtu 1420 up
sudo ip -n "$NS" route add default dev wg-etxea

# DNSa ere tuneletik (GitHub-eko 127.0.0.53 ez dago namespace-tik eskuragarri)
sudo mkdir -p "/etc/netns/$NS"
printf 'nameserver 1.1.1.1\nnameserver 9.9.9.9\n' | sudo tee "/etc/netns/$NS/resolv.conf" >/dev/null

kodea=$(sudo ip netns exec "$NS" curl -s -o /dev/null -w '%{http_code}' --max-time 20 \
  -A "kulturaInguruan/0.1" "$PROBA_URL" || true)
if [ "$kodea" = "200" ]; then
  echo "VPN ondo: robotaren eskaera guztiak etxetik (Cultura Navarra: $kodea)"
else
  echo "::warning::VPN piztuta, baina Cultura Navarra-k $kodea erantzun du; VPNrik gabe jarraituko da"
  sudo ip netns del "$NS"
  exit 1
fi
