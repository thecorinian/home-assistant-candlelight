# Home Assistant Candlelight

Warm-white candlelight with an **80% baseline**, quiet irregular motion, deeper gust-driven dips, and occasional rebounds to 100%. The brightness floor is 25%. Color temperature stays at 2000 K, clamped to each bulb's supported range. There is no hue cycling. Lights that support dimming but not color temperature keep their existing color.

The effect is inspired by a damped flame response; it is not a combustion or fluid simulation. Four overlapping waves provide small fluctuations. Randomly spaced gusts use a smoothed onset and decaying oscillation. Each bulb has a distinct phase and response delay. The event schedule extends without resetting the flame's clock.

## Install through Home Assistant

1. In **Settings → Devices & services → Helpers**, create a Toggle named **Natural Candlelight Active**. Confirm its entity ID is `input_boolean.natural_candlelight_active`.
2. In **Settings → Automations & scenes → Scripts**, create a script, choose **Edit in YAML**, and paste `scripts/natural_candlelight.yaml`. Confirm its entity ID is `script.natural_candlelight`.
3. Create a second script using `scripts/stop_natural_candlelight.yaml`. Confirm `script.stop_natural_candlelight`.
4. Create an automation using **Edit in YAML** and `automations/nightly_natural_candlelight.yaml`. Save it as **Nightly Natural Candlelight** and leave it enabled.

The nightly automation runs from **9:00 PM in Home Assistant's configured local time until local sunrise**, using Home Assistant's Sun integration. It handles startup during the window and a light switching on. It leaves off lights off and includes newly discovered eligible lights. Unavailable lights and on/off-only lights are skipped. At sunrise the effect stops and bulbs still on settle at 80%; this generic configuration does not impose a daytime lighting routine.

To activate it immediately during that window, stop any manually selected group, wait for Natural Candlelight to become idle, then choose **Run actions** on the nightly automation.

## Controls

Run **Natural Candlelight** from its script menu. Choose any bulbs, or leave the selection empty for all available dimmable lights. Set **Only lights already on** to preserve off bulbs. An optional duration in minutes stops automatically; zero runs until stopped. Only one group runs at a time. Stop it before changing the selection.

Run **Stop Natural Candlelight** to settle the currently lit bulbs at 80%. To keep the effect disabled for the night, also disable **Nightly Natural Candlelight**; otherwise switching a light on can start it again. Turning an individual bulb off removes it from the effect.

The Active helper is a stop/status control: turning it off stops the running effect. Turning it on alone does not launch the script. Use the scripts to start and stop.

## Adapt to an installation

At the top of the main script, `excluded_lights` can list broken or unwanted lights. `pause_helpers` and `pause_automations` can pause a competing adaptation system. A listed automation is briefly stopped and re-enabled, so it must be gated by one of the listed helpers. Configure any desired sunrise resumption in the nightly automation. The repository defaults contain no household entity IDs or credentials.

Commands are serialized with a short randomized pause. This avoids an uncontrolled burst of parallel requests, but larger groups update more slowly. Smart-bulb/cloud latency also limits smoothness; this is not a high-frequency hardware candle effect. Changing brightness or color manually while the effect runs may be overwritten; stop the effect first.

The 80% value is the baseline, not the average. Frequent downward gusts lower the time-average brightness. The requested 25–100% range is a bound, not a promise that every cycle will reach both ends.

## Validation

```sh
python3 -m pip install -r requirements-dev.txt
python3 -m unittest discover -s tests -v
```

Tests render the shipped Jinja selection and model templates to check off/unavailable exclusions, event continuity and pruning, brightness bounds, and different bulb responses. They do not emulate Home Assistant's scheduler or Tuya's physical response. Installation and live integration tests are recorded separately from these deterministic checks.
