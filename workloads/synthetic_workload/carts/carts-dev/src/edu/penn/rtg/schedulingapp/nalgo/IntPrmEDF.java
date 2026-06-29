package edu.penn.rtg.schedulingapp.nalgo;

import edu.penn.rtg.schedulingapp.basic.IntPRM;
import edu.penn.rtg.schedulingapp.basic.PeriodicRM;
import edu.penn.rtg.schedulingapp.basic.ResModel;
import edu.penn.rtg.schedulingapp.basic.Workload;

public class IntPrmEDF implements PrmAlgo {
	private int limit=50;
	Workload w;
	
	public IntPrmEDF(Workload w) {
		this.w = w;
	}

	@Override
	public ResModel getRes() {
		ResModel minRes=new IntPRM(0,0);
		ResModel res;
		double minUtil=2;
		PeriodicRmEDF algo=new PeriodicRmEDF(w,0);
		for(int i=1;i<limit;i++) {
			algo.setPeriod(i);
			res=algo.getRes();
			res=new IntPRM((PeriodicRM) res);
			//res.display();
			if(res.getUtil()<minUtil) {
				minUtil=res.getUtil();
				minRes=res;
			}
		}
		return minRes;
	}

	public void setLimit(int limit) {
		// TODO Auto-generated method stub
		this.limit=limit;
	}

}
