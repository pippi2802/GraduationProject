CC      ?= cc
CFLAGS  ?= -O2 -std=c11 -Wall -Wextra -D_GNU_SOURCE -pthread
LDFLAGS ?= -pthread -lrt

SRC := $(wildcard src/*.c)
OBJ := $(SRC:.c=.o)
BIN := rt-workload

.PHONY: all clean

all: $(BIN)

$(BIN): $(OBJ)
	$(CC) $(CFLAGS) -o $@ $(OBJ) $(LDFLAGS)

src/%.o: src/%.c
	$(CC) $(CFLAGS) -c -o $@ $<

clean:
	rm -f $(OBJ) $(BIN)
