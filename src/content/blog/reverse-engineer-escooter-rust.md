---
title: 'Rewriting e-scooter firmware in Rust: a dev log'
description: 'A practical dev log about reverse engineering an e-scooter and rebuilding its firmware in Rust, focusing on tools, architecture, and safety.'
pubDate: 'Sep 14 2026'
heroImage: '../../assets/blog-placeholder-2.jpg'
---

I spent a few weekends reverse engineering an e-scooter and then rebuilding its firmware stack in Rust. This is a practical log of the approach I took: how I located interfaces, sketched a safe firmware architecture using embedded Rust crates, and verified behavior on a bench before riding. This is not a how-to for bypassing locks or evading regulations — it's a developer-focused writeup about hardware, protocols, and embedded software choices.

## First pass: hardware, interfaces, and data collection

Start with observation and minimal invasion. I photographed the PCB, traced visible nets, and looked up the major chips. Typical targets are the MCU, a motor controller (often a separate MOSFET array or dedicated ESC), and radio/BLE modules. From there I tried to find exposed pads for UART, SWD, CAN, or an SPI bus.

A practical checklist I use:
- Identify the MCU by package markings and search the web for pinouts.
- Find test pads and continuity-test them back to the MCU pins.
- Attach a logic analyzer to suspected UART/TX/RX pads and capture boot logs.
- Scan for BLE advertising with a smartphone or nRF Connect to understand the radio surface APIs.

Example: when you find a UART boot log, the output often contains the chip bootloader message or a kernel log that helps confirm the CPU and clock speed. If the bootloader is locked, you can still observe runtime traffic on CAN or UART between the scooter ECU and the motor controller. Use a cheap logic analyzer and sigrok/ PulseView to record. Look for repeating frames to identify control messages.

A note on safety and legality: do not attempt to alter firmware on devices where you do not have ownership or permission. In many regions modifying powertrain controls can be illegal or unsafe.

## Reverse-engineering messages and building a model

Before writing Rust, I built a message model. That means mapping inputs (throttle, brake, sensors) to outputs (PWM to motor controller, battery management messages, lights). I logged these while operating the scooter at low speeds on a bench rig.

Typical work flow:
- Put the scooter on a stand so wheels can spin freely.
- Use the original controller to exercise throttle/brake and capture every bus (UART, CAN, BLE).
- Look for message fields that change monotonically with throttle — those are likely the command fields.
- Use differential testing: change one input at a time and correlate with observed fields.

I built a small Python tool to parse the recorded frames and generate a CSV of candidate fields vs throttle. This made it faster to identify which bytes mattered.

## Firmware design in Rust

My goals were safety, small runtime, and using idiomatic embedded-Rust crates. Key choices:
- no_std environment with cortex-m-rt (or appropriate runtime for the chip).
- Use embedded-hal traits where possible so driver code is portable.
- Keep control loops simple and well-tested: a closed-loop PI with rate limiting and software interlocks.
- Use heapless or statically allocated buffers; avoid dynamic allocation.

A tiny example structure (pseudocode):

```rust
use embedded_hal::serial::Read;
use embedded_hal::PwmPin;

struct Controller<RX, PWM> {
    uart_rx: RX,
    motor_pwm: PWM,
}

impl<RX: Read<u8>, PWM: PwmPin> Controller<RX, PWM> {
    fn step(&mut self) {
        if let Ok(b) = self.uart_rx.read() {
            // parse message and map to duty cycle
        }
        // safety checks: battery voltage, temp, brake status
        // update motor_pwm.set_duty(duty)
    }
}
```

For peripherals I used crates that implement the MCU HAL where available. For concurrency, I kept a single main loop at a fixed tick (e.g., 1 kHz) and interrupt-driven UART/CAN receive. For larger projects, RTIC gives a structured concurrency model, but it adds complexity.

Key safety patterns to implement in firmware:
- Watchdog to recover from stuck states
- Hard thresholds (max current, max duty) enforced in firmware, not just UI
- Redundant checks for brake and throttle: if brake active => zero torque
- Graceful fallback: if the custom firmware fails, publish a mode that limits speed and allows the user to dismount safely

## Testing, flashing, and incremental verification

I never flashed untested code straight to the scooter. My verification steps:
- Unit tests and model tests for control math on the host machine.
- Hardware-in-the-loop: run the controller against an emulator or bench motor and power supply.
- Use probe tools (OpenOCD or probe-rs) to flash with a recovery option.

When flashing, keep a serial console and a physical kill-switch accessible. Monitor battery voltage and current from separate instruments. If the board supports SWD/JTAG and it's unlocked, use probe-rs or an ST-Link to flash. If the bootloader is locked, stay at the interface level (build an adapter that intercepts and replays messages) rather than trying to break lock.

A final verification step: run low-power, limited-range tests in a controlled area before any street use.

## Lessons and next steps

Reverse engineering an e-scooter is mostly about methodical observation and incremental substitution. Rust made the firmware pleasant to work with: the type system encouraged explicit handling of error paths and ownership of shared resources. The embedded ecosystem (embedded-hal, heapless, cortex-m crates) covers most needs, but expect to write glue code for the device-specific motor controller or battery management protocol.

My next steps are adding more telemetry, improving the motor control loop with a logged datalogger, and exploring OTA update mechanisms that verify signatures so the board remains auditable after changes. If you try something similar, plan for rollback, hardware kill-switches, and clear documentation of every probe and test you run.