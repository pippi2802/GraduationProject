# model4 — IRQ steering (off vs on)

**Question:** does steering device IRQs **onto** the RT core inflate the delay layer
(R − C)? Two arms with identical manifests; only IRQ affinity differs.
**Expect:** compare δ / R-tail between arms. Often small — the unsteerable local-timer
tick dominates and Azure device IRQs are few; each cell logs the evidence to judge.

## Run
```bash
./build.sh
bash node-prep/apply.sh model4
python calibrate.py model4
python generate_yaml.py model4
PIN_RTCPU=0 IRQ_STEER=off OUT_TAG=_off ./run_job.sh model4   # IRQs parked AWAY from the RT core
PIN_RTCPU=0 IRQ_STEER=on  OUT_TAG=_on  ./run_job.sh model4   # IRQs steered ONTO the RT core
python result.py compare model4_off model4_on
```

Prereq: worker labelled `experiment-model=model4`.

**Why `PIN_RTCPU=0`:** keeps every cell (both arms) on the same core so the comparison is
apples-to-apples; without it the driver wanders and adds placement noise.

Ground truth per cell (proves whether IRQs actually reached the core):
```bash
cat results/model4_off/soft/U0.1/irq.json
# steered_ok / rejected = how many device IRQs Azure let us move;
# irqs_on_rtcpu_during_run = interrupts serviced on the RT core during the run.
```
The steering mechanism is `node-prep/steer-irqs.sh`.
