package edu.penn.rtg.schedulingapp.nalgo;

import edu.penn.rtg.schedulingapp.basic.PeriodicRM;
import edu.penn.rtg.schedulingapp.basic.ResModel;
import edu.penn.rtg.schedulingapp.basic.Workload;
import edu.penn.rtg.schedulingapp.util.Debug;

public class PeriodicRmEDF implements PrmAlgo {
	Workload w;
	int period;

	public PeriodicRmEDF(Workload w, int period) {
		this.w = w;
		this.period = period;
	}

	@Override
	public ResModel getRes() {
		int lcm=w.computeLCM();
		double d=0;double old_d=0;
		double max_exec=-1;
		double exec=0;
		for(int t=0;t<=lcm;t++)
		{
			d=w.demand_EDF(t);
			//Debug.prn(d);
			if(d==old_d) continue;
			exec=getExec(t,d);
			if(max_exec==-1) {
				max_exec=exec;
			}
			else if(max_exec<exec) {
				max_exec=exec;
			}
			//System.out.println(t+","+d+","+bw);
			old_d=d;
		}
		max_exec=Math.max(0,max_exec);
		return new PeriodicRM(period,max_exec);
	}

	private double getExec(int t, double d) {
		int k=(int) Math.floor(t/period);
		int lim =(k+1)*period-t;
		
		// case 1 : k = floor (t/p) if e>= lim
		int kstar = k;
		double e1=(double)(d+(kstar+2)*period-t)/(kstar+2);
		double rem_t=t-(period-e1)-kstar*period;
		if(!(e1>period-rem_t)) {
			if(kstar!=0) 
				e1=(double)d/kstar;
			else
				e1=d;
		}
		if(!(e1>=lim)) {
			e1=period+1;
		}
		
		// case 2 : k = floor (t/p) -1 if e>= lim
		kstar=k-1;
		double e2=(double)(d+(kstar+2)*period-t)/(kstar+2);
		rem_t=t-(period-e2)-kstar*period;
		if(!(e2>period-rem_t)) {
			if(kstar!=0) 
				e2=(double)d/kstar;
			else
				e2=d;
		}
		if(!(e2<lim)) {
			e2=period+1;
		}
		
		return Math.min(e1, e2);
	}

	public void setPeriod(int p) {
		period=p;
	}

}
