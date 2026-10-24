# Home Assistant Candlelight

Warm-white candlelight with **held 80%, 70%, and 50% baselines**, quiet irregular motion, deeper gust-driven dips, and occasional rebounds to 100%. The brightness floor is 25%. Color temperature stays at 2000 K, clamped to each bulb's supported range. There is no hue cycling. Lights that support dimming but not color temperature keep their existing color.

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

The effect starts at 70%. It then chooses each next baseline from `[80, 80, 70, 50]`: approximately 50% of target selections at 80%, 25% at 70%, and 25% at 50%. Each change uses a smoothstep ease over a random 15–30 seconds, then holds for a randomly selected 30–180 seconds. Both the fade duration and hold duration vary independently of the chosen level. Hold duration is independent of the selected brightness, so the time shares approach the same weights over longer runs, with finite-run variation and time spent between levels during blends. Consecutive choices may repeat. The same underlying baseline applies to the group; each bulb retains its individual flicker and gust response.

These values are baselines, not a flat output or the average. Their weighted nominal average is 70%; downward gusts lower the actual time-average brightness further. The requested 25–100% range is a bound, not a promise that every cycle will reach both ends.

## Validation

```sh
python3 -m pip install -r requirements-dev.txt
python3 -m unittest discover -s tests -v
```

Tests render the shipped Jinja selection and model templates to check off/unavailable exclusions, event continuity and pruning, brightness bounds, different bulb responses, baseline transition continuity, and weighted dwell distribution. They do not emulate Home Assistant's scheduler or Tuya's physical response. Installation and live integration tests are recorded separately from these deterministic checks.

## Optional timed wind experiment

`experiments/candlelight_wind_trial.yaml` models occasional light gusts as a random mix of single deep dips and loose three-pulse flutters. It waits 40–100 seconds after each episode before the next, with an 8–14-second opening delay. Single dips fall toward 20–40% of the current baseline (bounded at 20% absolute brightness), then return near the baseline without an added oscillating tail. Triplets use varied dips and rebounds, followed by a brief gentle damped tail. Each pulse uses six brightness frames to soften the fall and recovery. Near-full rebounds are occasional rather than routine.

This experiment targets a long-run 30%/40%/30% mix of 80%, 70%, and 50% baseline selections, retaining 30–180-second holds. Every completed 50% hold must leave the low state: two rapid brightness commands rise to a random 90–100% peak, hold briefly, then ease down toward 70% or 80% over 4–7 seconds. Other baseline changes retain 15–30-second eased blends. A low hold chooses its successor from `[70,70,80]`; other holds choose from `[50,50,50,70,70,80,80]`. This prevents consecutive low holds while preserving the long-run target mix. The brief flare changes actual brightness time shares; these are target-selection weights, not exact output percentages. Gusts are deferred for at least 15–25 seconds after the rebound starts settling. The everyday model retains its original 50%/25%/25% target weights. Broad gentle turbulence and slow wandering continue between gusts; there are no independent frequent background gusts. A 1.3-second first-order filter smooths this surrounding motion. Warm-white color remains fixed. The experimental brightness floor is 20%; the everyday model's floor is 25%. Actual burst speed and smoothness depend on the integration and bulbs.

Install it as a separate script with entity ID `script.candlelight_wind_trial`. Run normal Natural Candlelight first, then run the trial and choose the bulbs to test. Set Duration to 1–60 minutes; it defaults to three minutes. Only currently-on bulbs participate. The trial temporarily pauses the nightly automation, moves the normal controller to the other bulbs, and runs the selected group for the chosen duration. It then restarts the normal model on all currently-on eligible lights and restores the nightly automation's previous enabled state. The model is experimental and is not selected by the nightly automation.

Allow the timed trial to finish. If you interrupt it through `script.turn_off` or restart/reload Home Assistant, its final cleanup actions cannot run. Recovery: stop both scripts, turn the Active helper off, restart Natural Candlelight with `only_on: true`, and re-enable the nightly automation if you normally use it. The trial intentionally resumes the normal model on all lit bulbs rather than restoring a previous manually selected subgroup.

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
