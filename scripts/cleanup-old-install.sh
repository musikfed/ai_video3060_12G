#!/usr/bin/env bash
# Dedicated ai_video3060_12G cleanup. DRY-RUN by default.
set -euo pipefail
SRC=/1tbdisk/ai_video3060_12G
DATA=/1tbdisk/ai_video3060_12G-data
UNITDIR="$HOME/.config/systemd/user"
UNIT1=peginelab-video-studio.service
UNIT2=peginelab-wan-comfy.service
case "$*" in
  --execute) ACTION=delete ;;
  --dry-run|"") ACTION=preview ;;
  *) echo "Use --dry-run or --execute" >&2; exit 2 ;;
esac
echo "Only old PEGINELAB video project will be removed:"
for p in "$SRC" "$DATA"; do
  if test -e "$p"; then du -sh -- "$p"; else echo "Absent: $p"; fi
done
for u in "$UNIT1" "$UNIT2"; do
  echo "User unit: $UNITDIR/$u"
  if test -f "$UNITDIR/$u"; then grep -E '^(ExecStart|WorkingDirectory|Environment)=' "$UNITDIR/$u" || true; fi
done
if [[ "$ACTION" == preview ]]; then
  echo "DRY-RUN only. Save any important MP4/PNG before deletion."
  echo 'To remove: VIDEO_STUDIO_CONFIRM=DELETE_AI_VIDEO3060_12G bash scripts/cleanup-old-install.sh --execute'
  exit 0
fi
[[ "$(printenv VIDEO_STUDIO_CONFIRM || true)" == DELETE_AI_VIDEO3060_12G ]] || {
  echo "Confirmation missing. No deletion." >&2; exit 3;
}
mountpoint -q /1tbdisk || { echo "Mount /1tbdisk missing" >&2; exit 4; }
for p in "$SRC" "$DATA"; do
  [[ ! -L "$p" ]] || { echo "Refusing symlink $p" >&2; exit 5; }
  if [[ -e "$p" ]]; then
    [[ "$(realpath -e -- "$p")" == "$p" ]] || exit 5
    [[ "$(findmnt -n -o TARGET -T "$p")" == /1tbdisk ]] || exit 5
  fi
  if findmnt -rn -o TARGET | grep -Fqx -- "$p"; then
    echo "Refusing mounted directory $p" >&2; exit 6
  fi
  if findmnt -rn -o TARGET | grep -F -- "$p/" | grep -q .; then
    echo "Refusing nested mount $p" >&2; exit 6
  fi
done
for u in "$UNIT1" "$UNIT2"; do
  path="$UNITDIR/$u"
  if [[ -e "$path" ]]; then
    [[ -f "$path" && ! -L "$path" ]] || exit 7
    if ! grep -Fq -- "$SRC" "$path" && ! grep -Fq -- "$DATA" "$path"; then
      echo "Unexpected unit: $path" >&2; exit 7
    fi
  fi
done
if [[ -f "$DATA/gpu-session.lock" ]]; then
  exec 9<"$DATA/gpu-session.lock"
  flock -n 9 || { echo "GPU job still running" >&2; exit 8; }
fi
systemctl --user disable --now "$UNIT1" "$UNIT2" 2>/dev/null || true
for u in "$UNIT1" "$UNIT2"; do
  if systemctl --user is-active --quiet "$u"; then
    echo "Service $u still active; refusing deletion." >&2; exit 9
  fi
done
rm -f -- "$UNITDIR/$UNIT1" "$UNITDIR/$UNIT2"
systemctl --user daemon-reload
if [[ -d "$DATA" ]]; then rm -rf --one-file-system -- "$DATA"; fi
if [[ -d "$SRC" ]]; then rm -rf --one-file-system -- "$SRC"; fi
echo "Old project deleted; shared Ollama and unrelated services untouched."
