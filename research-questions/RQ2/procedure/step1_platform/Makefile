CC ?= cc
CFLAGS ?= -O2 -Wall -Wextra

.PHONY: all clean
all: enemy victim

enemy: enemy.c
	$(CC) $(CFLAGS) -o enemy enemy.c

victim: victim.c
	$(CC) $(CFLAGS) -o victim victim.c

clean:
	rm -f enemy victim
