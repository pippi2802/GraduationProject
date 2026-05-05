CL=""
N=0
while read q t d
 do
  c=$((q-1000))
  p=$t
  echo C=$c P=$p Q=$q T=$t
  CL="$CL -C $c -p $p -q $q -t $t"
  N=$((N+1))
 done
CL="$EXTRA_ARGS $CL -n $N"

echo $CL
sudo ./periodic_thread $CL
