#!/usr/bin/env bash

export HISTFILESIZE=
export HISTIGNORE="&:[bf]g:exit:ls:history:clear"
export HISTSIZE=
export HISTTIMEFORMAT="[%F %T] "
export HISTCONTROL="erasedups:ignoreboth"

export PROMPT_DIRTRIM=2

# if no command is running disconnect after three minutes of inactivity
export TMOUT=180

shopt -s cmdhist
shopt -s histappend

LS_OPTIONS='--group-directories-first --color=auto'

# shellcheck disable=SC2139
alias l="ls -hF $LS_OPTIONS"
# shellcheck disable=SC2139
alias ls="ls -hF $LS_OPTIONS"
# shellcheck disable=SC2139
alias l1="ls -hF1 $LS_OPTIONS"
# shellcheck disable=SC2139
alias ll="ls -hlF $LS_OPTIONS"
# shellcheck disable=SC2139
alias lrt="ls -hlFrt $LS_OPTIONS"
# shellcheck disable=SC2139
alias lx="ls -hlFX $LS_OPTIONS"
# shellcheck disable=SC2139
alias lll="ls -ahlF $LS_OPTIONS"

RED='\033[1;31m'
GREEN='\033[38;05;34m'
GRAY='\033[38;05;239m'
LIGHT_GRAY='\033[38;05;235m'
MEDIUM_GRAY='\033[38;05;244m'
NOTHING='\033[0m'

SLASH="/"

if [ ! "$ENV" == "development" ]
then
  printf '\033]6;1;bg;red;brightness;255\a'
  printf '\033]6;1;bg;green;brightness;0\a'
  printf '\033]6;1;bg;blue;brightness;0\a'

  COLOR=$RED
else
  COLOR=$GREEN
fi

on_exit() {
  printf '\033]6;1;bg;*;default\a'
}

trap on_exit EXIT

PS1='\['$COLOR'\]'$ENV'\['$LIGHT_GRAY'\]'$SLASH'\['$GRAY'\]'$CUSTOMER_IDENTIFIER' \['$MEDIUM_GRAY'\]\w\['$NOTHING'\] '

[ -n "$TERM" ] && [ -r /etc/motd ] && cat /etc/motd

ENV_ART=$(echo "$ENV" | figlet)

echo -e "${COLOR}${ENV_ART}${NOTHING}"
echo
echo
