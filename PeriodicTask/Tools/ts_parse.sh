args_gen()
{
  N=0
  while read C D T;
   do
    PRIO=$((99-N))
#    WCET=$((C*1000))
#    PERIOD=$((T*1000))
    WCET=$C
    PERIOD=$T
    echo -n " -C $WCET"
    echo -n " -p $PERIOD"
    echo -n " -P $PRIO"
    N=$((N+1))
   done
  echo " $EXTRA_ARGS -n $N"
}

ARGS=$(args_gen < $1)

echo "./periodic_thread $ARGS"
./periodic_thread $ARGS
