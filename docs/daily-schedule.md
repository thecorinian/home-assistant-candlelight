# Daily solar and weather schedule

This optional controller replaces the legacy 9 PM-to-sunrise automation. It uses Home Assistant's local timezone, Sun integration and a weather entity. Configure room lists before enabling it: an empty exclusion list includes all available dimmable lights.

## Installation

1. Install Natural Candlelight, Lighting Manual Off Registry, Lighting Off Priority, Lighting Off Wins, and Resume Automatic Lighting from the main README. Update their YAML together when upgrading.
2. Create a Toggle **Daily Lighting Schedule Active** (`input_boolean.daily_lighting_schedule_active`). Leave it off during setup.
3. Create four Text helpers with minimum length 0 and maximum 255: **Lighting Schedule Clock**, **Lighting Schedule Frame**, **Lighting Schedule On Targets**, and **Lighting Schedule Off Targets**. Confirm their IDs are `input_text.lighting_schedule_clock`, `input_text.lighting_schedule_frame`, `input_text.lighting_schedule_on_targets`, and `input_text.lighting_schedule_off_targets`. Initialize them to empty strings.
4. Install `scripts/daily_lighting_controller.yaml` as `script.daily_lighting_controller`, then `automations/daily_lighting_schedule.yaml` as `automation.daily_lighting_schedule`.
5. Edit the controller's `weather_entity`, `excluded_lights`, `outdoor_lights`, `bedroom_lights`, `morning_bright_lights`, and `circulation_lights`. Put outdoor entities in the candlelight script's exclusions too. Keep scheduled outdoor bulbs **out of Lighting Off Wins' exclusions**, so manual outdoor commands also create holds; remove any outdoor exclusions left from an indoor-only installation. Configure `alternating_week_lights` and `alternating_week_start` consistently in all automatic controllers; the example date is only a placeholder. Map dome partners in both off-priority files' `coupled_fixtures` lists.
6. Disable Nightly Natural Candlelight and competing solar/sunrise automations. Stop running color, outdoor-cycle, sunrise, and candle scripts. Keep Lighting Off Wins enabled.
7. Enable the new schedule automation, then turn on **Daily Lighting Schedule Active**. Existing manual holds survive initial activation. Check the Frame and Clock helpers and the controller trace.

Turn off the Daily toggle to pause this routine before manually previewing another effect. Stop Natural Candlelight too if needed. Legacy effect scripts have their own handback behavior and are not separate simultaneous owners of scheduled lights. Keep a backup of the prior YAML and automation enabled states.

## Indoor timing

| Phase | Local timing | Commanded brightness |
|---|---|---|
| Night | 10 PM to sunrise | Off, unless manually overridden |
| Wake | Sunrise to +45 minutes | Smooth rise from minimum to 80%; kitchen/dining list up to 100%, circulation list 60% |
| Morning | Next 60 minutes | Hold morning targets |
| Daylight taper | End of hold to 11:30 AM | Smooth taper to off |
| Day | 11:30 AM to evening start | Off; dark-weather shared-room fallback 25%, bedrooms off |
| Evening arrival | Sunset −45 minutes to +30 minutes | Up to 70% shared, 50% bedrooms, 40% circulation |
| Wind-down | 7–10 PM | Ceiling falls through 70%, 35% at 8 PM, 15% at 9 PM, and zero at 10 PM |
| Candlelight | From 7:30 PM until off | Approved flame motion scaled under the current common ceiling |

The bedtime ceiling wins over a late summer sunset. Dark weather starts the evening ramp 30 minutes earlier. Late sunrise shortens the morning phases. Solar times are cached daily and corrected at the actual sun events; a first installation after a sun event approximates today's event using the next event's local time. No indoor illuminance sensor is assumed, so dark-weather support is an estimate.

Candlelight uses the existing random baseline holds, flutter, gusts, loose triplets and rebounds. Its 80% reference level is scaled to the schedule; even a 100% model peak cannot exceed the scheduled ceiling. Scheduled shutdown skips the legacy 80% cleanup. At very low levels the bulb's minimum 1% command applies until off.

## White temperature

Temperature matching is an aesthetic preference. At 50°F/10°C or below, including 42°F, the requested white is 2000 K, clamped to each bulb's supported range.

| Outdoor temperature | Daytime white |
|---|---|
| ≤50°F | 2000 K |
| 65°F | 2700 K |
| 75°F | 3500 K |
| 85°F | 4500 K |
| ≥90°F | 5000 K |

Interpolate between anchors. Evening white ranges from 2000 K at 50°F to 2700 K at 85°F, then returns toward 2000 K from 9–10 PM. Wake-up begins warm. White changes are limited to 2.5 K/second and quantized to 25 K commands; the largest 3000 K change therefore takes about 20 minutes. On controller startup, the current target is used immediately.

## Weather motifs

Conditions must persist at least ten minutes. A roughly 90-second entry motif and two-minute windows every half hour provide noticeable decoration: blue/white rain waves, white/deep-blue snow or frost-risk breaths, faster steel-blue hail swells, warm-white wind dips, and diffuse fog breathing. They share elapsed-time phases, including within domes, but cloud dispatch is not perfectly simultaneous. There are no lightning flashes.

Indoor color motifs stop when evening candlelight begins. The approved warm-white candle motion remains the default after 7:30 PM; weather still adjusts white temperature. Outdoors may retain colored motifs overnight. Frost risk is inferred from near-freezing temperature and dew point, not measured frost. Celsius and common wind-speed units are converted. Weather older than two hours or unavailable falls back to warm white with no motifs. Condition precedence is rain, snow, hail, fog, frost risk, then wind.

## Outdoors and alternating weeks

Outdoor entities start a 30-minute fade at sunset toward 50%. They step gradually toward 25% after 10 PM and 18% after midnight. The dawn fade runs from sunrise −45 minutes to −15 minutes. Rejoining a current nonzero phase uses steps of at most 5 percentage points per loop (about two seconds plus service latency). No per-segment string-light control is implied.

Children's entities are excluded during alternate absent weeks. Local wall-clock week arithmetic preserves a configured Friday 4 PM handoff across daylight-saving changes. They remain manually controllable. Configure the real anchor locally; none is published in the generic files.

## Manual control and verification limits

A direct Home Assistant light on/off/brightness/color command creates a persistent fixture hold until the next 4 AM local reset. Expected schedule power acknowledgments are ignored for a short window. The guard ignores unattributed service calls and the first 90 seconds of bulb state feedback after startup or automation reload, preventing initial cloud synchronization from creating false holds. Authenticated direct commands remain protected during that interval. The daily reset also catches up after downtime; initial activation preserves existing holds. Resume Automatic Lighting clears selected holds, or all with an empty selection; the controller then rejoins the current phase.

The registry uses an `h:` prefix plus eight-character SHA256 tokens, up to 31 held entities. The prefix prevents numeric-looking token strings from being reinterpreted. Updates are queued; malformed state, capacity overflow or a detected collision fails closed with `*`. This encoding is not a security mechanism. Expected-power marker helpers also support at most 31 targets per batch.

Google commands routed directly to Tuya can deliver delayed or missing state. Brightness and color intent cannot reliably be inferred from that feedback. Route Google through Home Assistant and test the real command path before relying on voice overrides. Even then, cloud/device response can be delayed. An entity reporting on does not prove the physical bulb is on.

The controller checks every two seconds but sends only changed values or a two-minute refresh. Candlelight retains its faster frame traffic. This is not a measured Wi-Fi load or Tuya quota guarantee. Offline bulbs are skipped; a device silently retaining stale on-state may still receive unsuccessful commands.

## Basis and tests

The schedule follows the broad principle of stronger daytime light, dimmer evenings and darkness during sleep. The relevant consensus concerns healthy adults and measured melanopic light at the eye; bulb percentages and Kelvin alone cannot demonstrate compliance. The outdoor-temperature mapping and decorative motifs are design choices. [Brown et al., PLOS Biology](https://journals.plos.org/plosbiology/article?id=10.1371/journal.pbio.3001571)

Weather attributes vary by integration. [Home Assistant weather documentation](https://www.home-assistant.io/integrations/weather/)

Run the repository tests, Home Assistant's configuration check, and live traces. Tests cover solar/bedtime boundaries, temperature ranges, weather age, manual acknowledgments, holds and candle ceilings. They do not emulate physical bulbs. Validate sunrise, sunset, late-evening behavior and actual voice overrides in your home after installation.
