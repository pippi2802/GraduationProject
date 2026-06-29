package edu.penn.rtg.schedulingapp.nalgo;

import edu.penn.rtg.schedulingapp.basic.*;

public class EqvPrmEDF implements PrmAlgo{

    private int periodLimit=10000;
    public Workload w;
    
    public EqvPrmEDF(Workload w) {
            this.w = w;
    }

    @Override
    public ResModel getRes() {
            ResModel minRes = getInitRes();
            
            ResModel eqvMinRes = new EqvPrmModel(minRes.getTask().period, minRes.getUtil());
            return eqvMinRes;
    }
    
    public IntPRM getInitRes(){
    	IntPRM minRes=new IntPRM(0,0);
    	ResModel res;
    	double minUtil=2;
    	PeriodicRmEDF algo=new PeriodicRmEDF(w,0);
    	for(int i = 1; i <= periodLimit; i++) {
    		algo.setPeriod(i);
    		res=algo.getRes();
    		res=new IntPRM((PeriodicRM) res);
    		//res.display();
    		if(res.getUtil()<minUtil) {
    			minUtil=res.getUtil();
    			minRes=(IntPRM) res;
    		}
    	}
    	
    	return minRes;
    }

    public void setPeriodLimit(int limit) {
            this.periodLimit=limit;
    }

}
