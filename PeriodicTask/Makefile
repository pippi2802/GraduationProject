OBJS = rt_utils.o gettime.o cputime.o cpu_consume.o task.o rand1.o dl_syscalls.o output.o

CFLAGS += -Wall -Wextra -pedantic -std=c99
CFLAGS += -O0
LDLIBS = -lrt

all: periodic_task periodic_task_cfs periodic_thread
clean:
	rm -f *.o
	rm -f periodic_task periodic_task_cfs periodic_thread

periodic_task: periodic_task.o $(OBJS)

periodic_task_cfs: periodic_task_cfs.o $(OBJS)
periodic_thread: CFLAGS += -pthread
periodic_thread: LDFLAGS += -pthread
periodic_thread: periodic_thread.o $(OBJS) affinity.o

test.gz: fs/Test/periodic_thread fs/Test/periodic_task fs/Test/ts_parse.sh fs/Test/driver1.sh
	cd fs; find . | cpio -H newc -o | gzip > ../test.gz

fs/Test:
	mkdir -p fs/Test

fs/Test/%.sh: Tools/%.sh
	cp $< fs/Test

fs/Test/%: % fs/Test
	cp $< fs/Test
