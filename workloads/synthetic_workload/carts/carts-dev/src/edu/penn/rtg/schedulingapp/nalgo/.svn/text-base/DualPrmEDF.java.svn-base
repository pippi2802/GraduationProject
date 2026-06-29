package edu.penn.rtg.schedulingapp.nalgo;

import edu.penn.rtg.schedulingapp.basic.DualPRM;
import edu.penn.rtg.schedulingapp.basic.IntPRM;
import edu.penn.rtg.schedulingapp.basic.PeriodicRM;
import edu.penn.rtg.schedulingapp.basic.ResModel;
import edu.penn.rtg.schedulingapp.basic.Workload;

public class DualPrmEDF implements PrmAlgo{
	private int limit1=20;
	private int limit2=50;
	Workload w;

	public DualPrmEDF(Workload w) {
		this.w = w;
	}
	public ResModel getRes() {
		ResModel minRes=new IntPRM(0,0);
		ResModel res;
		double minUtil=2;
		PeriodicRmEDF algo=new PeriodicRmEDF(w,0);
		for(int i=1;i<limit1;i++) {
			algo.setPeriod(i);
			res=algo.getRes();
			res=new DualPRM((PeriodicRM) res);
			res=computeRem((DualPRM)res);
			//res.display();
			if(res.getUtil()<minUtil) {
				minUtil=res.getUtil();
				minRes=res;
			}
		}
		return minRes;
	}
	private ResModel computeRem(DualPRM res) {
		w.setRes1(res.getMajorRes());
		IntPrmEDF algo=new IntPrmEDF(w);
		algo.setLimit(limit2);
		res.setMinorRes((IntPRM)algo.getRes());
		w.setRes1(null);
		return res;
	}
	public void setLimit(int limit1,int limit2) {
		// TODO Auto-generated method stub
		this.limit1=limit1;
		this.limit2=limit2;
	}

}
