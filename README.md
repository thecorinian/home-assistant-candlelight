# Home Assistant Candlelight

Warm-white candlelight with continuous flutter, occasional single dips and loose triplets, and brief bright rebounds after long low holds. The approved wind model is now the **default controller**, including the nightly schedule. It starts at 50%, varies around held 50%, 70%, and 80% baselines, and bounds output to 20–100%. Color temperature stays at 2000 K, clamped to each bulb's supported range. Dimmable lights without color-temperature support keep their existing color.

The effect combines overlapping waves, randomized gusts, eased transitions, and a damped response. It approximates a flame's appearance; it is not a combustion or fluid simulation. The main controller runs continuously when Minutes is zero. The optional experiment remains available for timed comparisons but is no longer needed to get the approved effect.

## Install through Home Assistant

1. In **Settings → Devices & services → Helpers**, create a Toggle named **Natural Candlelight Active**. Confirm its entity ID is `input_boolean.natural_candlelight_active`.
2. In **Settings → Automations & scenes → Scripts**, create a script, choose **Edit in YAML**, and paste `scripts/natural_candlelight.yaml`. Confirm its entity ID is `script.natural_candlelight`.
3. Create a second script using `scripts/stop_natural_candlelight.yaml`. Confirm `script.stop_natural_candlelight`.
4. Create a third script using `scripts/sunrise_fade_off.yaml`. Confirm `script.sunrise_fade_off`.
5. Create an automation using **Edit in YAML** and `automations/nightly_natural_candlelight.yaml`. Save it as **Nightly Natural Candlelight** and leave it enabled.

The nightly automation runs from **9:00 PM in Home Assistant's configured local time until local sunrise**, using Home Assistant's Sun integration. It handles startup during the window, a light switching on, and a once-per-minute check that restarts an idle controller. It does not interrupt an active timed wind trial or sunrise fade. It leaves off lights off and includes newly discovered eligible lights. Unavailable lights and on/off-only lights are skipped.

At **local sunrise**, candlelight stops at its current brightness and all eligible lights already on gradually fade to off over **30 minutes**. Each bulb starts from its own brightness, using an eased curve with small updates about every 15 seconds. The fade preserves color and never raises a manually lowered brightness. Lights switched off remain off; lights newly switched on after the fade starts are outside its initial snapshot. Final off commands are retried up to three times, but an unreachable bulb cannot be guaranteed to respond. Home Assistant must be running at sunrise; an interrupted fade does not resume automatically after a restart.

To activate it immediately during that window, stop any manually selected group, wait for Natural Candlelight to become idle, then choose **Run actions** on the nightly automation.

## Controls

Run **Natural Candlelight** from its script menu. Choose any bulbs, or leave the selection empty for all available dimmable lights. **Only lights already on** is enabled by default to preserve off bulbs. An optional duration in minutes stops automatically; zero runs until stopped. Only one group runs at a time. Stop it before changing the selection.

Run **Stop Natural Candlelight** to settle the currently lit bulbs at 80%. To keep the effect disabled for the night, also disable **Nightly Natural Candlelight**; otherwise the next minute check or a light turning on can start it again. Turning an individual bulb off removes it from the effect.

The Active helper is a stop/status control: turning it off stops the running effect. Turning it on alone does not launch the script. Use the scripts to start and stop.

## Adapt to an installation

At the top of **both** the main script and the sunrise fade script, set the same `excluded_lights` list for broken or unwanted lights. In the main script, `pause_helpers` and `pause_automations` can pause a competing adaptation system. A listed automation is briefly stopped and re-enabled, so it must be gated by one of the listed helpers. The sunrise script's optional `resume_helpers` stay off during the fade and are turned on afterward. The repository defaults contain no household entity IDs or credentials.

Change `minutes: 30` in the automation's sunrise branch to adjust the fade duration (1–120 minutes). A manual **Stop Natural Candlelight** still settles lit bulbs at 80%; sunrise uses a separate stop path to avoid that brightness jump.

The model starts at 50%. Low baselines hold for 45–150 seconds, 70% holds last 30–75 seconds, and 80% holds last only 10–20 seconds. Consecutive targets cannot repeat. Lower states occupy more time; these are randomized holds, not exact output percentages. Every completed low hold gets a rapid rebound to 90–100%, a brief peak pause, then a 2–4-second eased settle. Other baseline changes blend over 10–20 seconds. Integration latency can extend these timings.

Random gust episodes mix single deep dips and loose three-pulse flutters, spaced 40–100 seconds after the previous episode. Each pulse uses six brightness frames to soften the fall and recovery. Four overlapping background waves, slow wandering, and a 1-second first-order filter keep the effect moving between gusts. Three staggered groups share background brightness within each group.

Each background group waits at least 500 ms or 100 ms per member after dispatch. With 24 bulbs the programmed pauses budget about ten background bulb updates per second before service overhead. Group dispatch and the faster gust/rebound bursts still create traffic; this is not a network-wide rate limiter or a Tuya quota guarantee. No router bandwidth or airtime measurements have been made. The official [HA Tuya integration](https://www.home-assistant.io/integrations/tuya/) is cloud based, so responsiveness depends on the integration and bulbs. Changing brightness or color manually while the effect runs may be overwritten; stop it first.

## Validation

```sh
python3 -m pip install -r requirements-dev.txt
python3 -m unittest discover -s tests -v
```

Tests render the shipped Jinja selection and model templates to check off/unavailable exclusions, continuous-run and stop guards, model parity with the approved trial, brightness bounds, pulse behavior, randomized dwell times, grouping, background pacing, and the sunrise fade's monotonic curve and manual-dimming behavior. They do not emulate Home Assistant's scheduler or Tuya's physical response. Installation and live integration tests are recorded separately from these deterministic checks.

## Optional timed wind experiment

`experiments/candlelight_wind_trial.yaml` retains the approved model as a separate timed comparison tool. Normal installation and the nightly schedule now use the same visual model directly, so this script is optional.

Install it as `script.candlelight_wind_trial`. Start Natural Candlelight first, then run the trial on selected currently-on bulbs for 1–60 minutes (default three). It pauses the nightly automation, moves the normal controller to other eligible lit bulbs, and restores the normal controller on all eligible lit bulbs when finished. It restores the nightly automation's previous enabled state. Its fixed initial group ordering does not pick up newly created entities until another run; the default controller refreshes grouping each pass.

Let a timed trial finish. If interrupted through `script.turn_off` or a Home Assistant restart/reload, its final cleanup cannot run. Recovery: stop both scripts, turn the Active helper off, restart Natural Candlelight with `only_on: true`, and re-enable the nightly automation if normally used. Disable the nightly automation before manually stopping the normal controller if it should remain off.

## Example action calls

Run a selected group (replace the example IDs):

```yaml
action: script.turn_on
target:
  entity_id: script.natural_candlelight
data:
  variables:
    lights:
      - light.example_lamp_1
      - light.example_lamp_2
    only_on: true
    minutes: 0
```

Run the optional experiment on the same group for 20 minutes:

```yaml
action: script.turn_on
target:
  entity_id: script.candlelight_wind_trial
data:
  variables:
    minutes: 20
    lights:
      - light.example_lamp_1
      - light.example_lamp_2
```

This project uses built-in Home Assistant scripts and automation actions. No HACS component or bulb-firmware modification is required. Bulbs must support dimming. Actual cadence depends on bulb count, the integration, and network/cloud latency; the model cannot guarantee physically smooth high-frequency flicker on every device.
