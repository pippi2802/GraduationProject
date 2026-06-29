CL=""
N=0
while read c p q t
 do
  echo C=$c P=$p Q=$q T=$t
  CL="$CL -C $c -p $p -q $q -t $t"
  N=$((N+1))
 done
CL="$CL -n $N"

echo $CL
sudo ./periodic_thread $CL
