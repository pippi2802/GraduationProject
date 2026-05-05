# Real-Time Periodic Tasks
This is taken from https://gitlab.retis.santannapisa.it/l.abeni/PeriodicTask and it is a kind of project for simulating periodic tasks on Linux with different schedulers.

It is interesting because these tasks can be simulated on your own device or in a container with the gcc image in Docker. 

This allows the experimental setup and it is indeed providing metrics and toold for measuring the execution time, CDF and deadline miss.

## Test the experiments
```bash
docker build -f docker/Dockerfile -t periodic-task:latest .
```
```bash
docker run --rm \
  --cap-add=SYS_NICE \
  -v /dev:/dev \
  periodic-task:latest \
  ./periodic_task -C 10000 -p 100000 -P 1 -N 50
```

Since an output is produces and printed, this can be saved automatically to the host machine if we execute:
```bash
docker run --rm --cap-add=SYS_NICE -v /dev:/dev periodic-task:latest \
  ./periodic_task -C 10000 -p 100000 -P 1 -N 50 > results/results.txt
```

This will execute only one task. So, if we want to execute more, we have either to run the following (for parallel execution):
```bash
docker run --rm --cap-add=SYS_NICE -v /dev:/dev periodic-task:latest \
  sh -c "./periodic_task -C 10000 -p 100000 -P 1 -N 50 > out1.txt & \
          ./periodic_task -C 10000 -p 100000 -P 2 -N 50 > out2.txt & \
          wait"
```

or this for sequential
```bash
docker run --rm --cap-add=SYS_NICE -v /dev:/dev periodic-task:latest \
  sh -c "./periodic_task -C 10000 -p 100000 -P 1 -N 50 && \
          ./periodic_task -C 10000 -p 100000 -P 2 -N 50"
```

Or we can also create scripts. Here an example on a multi-task scenario:
```bash
# Build the image
docker build -f docker/Dockerfile -t periodic-task:latest .

# Run the multi-task scenario
docker run --rm \
  --cap-add=SYS_NICE \
  -v /dev:/dev \
  -v $(pwd)/multitask_results:/PeriodicTask/multitask_results \
  periodic-task:latest \
  sh run_multitask_scenario.sh
```