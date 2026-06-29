package edu.penn.rtg.schedulingapp.algo;


import edu.penn.rtg.schedulingapp.ResourceModel;
import edu.penn.rtg.schedulingapp.SchedulingComponent;
import edu.penn.rtg.schedulingapp.util.SchException;
import edu.penn.rtg.schedulingapp.util.UserUtil;


public class EDFSchedulability_DPRM {
	private SchedulingComponent comp;
	//private Workload W;
	//private DualPRM RM;

	public EDFSchedulability_DPRM(SchedulingComponent C)
			throws Exception {
		if (!C.isEDF()) {
			UserUtil.show("The component has algorithm set to DM. Cannot continue");
			throw new SchException();
		}
		this.comp=C;
		/*
		this.W=new Workload();
		Vector<Task> tasks=C.getTasks(C.getSize((int) C.getMaxPeriod()));
		for(Task t:tasks) {
			W.addTask((int)t.getPeriod(),(int)t.getExecution(),(int)t.getDeadline());
		}
		*/
	}
	/*
	public int getPeriod1() {
		PrmAlgo ip=new DualPrmEDF(W);
		RM=(DualPRM) ip.getRes();
		return RM.getPeriod1();
	}
	public int getExec1() {
		return RM.getExec1();
	}
	public int getPeriod2() {
		return RM.getPeriod2();
	}
	public int getExec2() {
		return RM.getExec2();
	}
	*/

	public int getMaxPeriod(double k) {
		int lcm=comp.computeLCM_DPRM();
//		System.out.println( lcm);
		int dem=0,oldDem=0;
		double p=0,minp=-1;
		for(int t=0;t<=lcm;t++) {
			dem=comp.computeDBF_DPRM(t);
			//System.out.println(t+","+dem+","+p);
			if(oldDem==dem) continue;
			oldDem=dem;
			p=(float)(k*t-dem)/(k*(1-k));
			if(minp==-1) minp=p;
			minp=Math.min(minp, p);
			//System.out.println(t+","+dem+","+p);
		}
		return (int)Math.ceil(minp);
		
	}
	public int getMaxExecution(double k) {
		int lcm=comp.computeLCM_DPRM();
		int dem=0,oldDem=0;
		double p=0,mine=-1;
		for(int t=0;t<=lcm;t++) {
			dem=comp.computeDBF_DPRM(t);
			if(oldDem==dem) continue;
			oldDem=dem;
			p=(float)(k*t-dem)/(1-k);
			if(mine==-1) mine=p;
			mine=Math.min(mine, p);
			//System.out.println(t+","+dem+","+p);
		}
		return (int)Math.ceil(mine);
		
	}

	public int getMaxExec(int p) {
		int lcm=comp.computeLCM_DPRM();
		int dem=0,oldDem=0;
		int e=0,maxe=0;
		for(int t=0;t<=lcm;t++) {
			dem=comp.computeDBF_DPRM(t);
			if(oldDem==dem) continue;
			oldDem=dem;
			e=(int)Math.ceil((float)((2*p-t)+Math.sqrt(Math.pow((2*p-t), 2)+8*p*dem))/4);
			maxe=Math.max(maxe, e);
			//System.out.println(t+","+dem+","+e);
		}
		return maxe;
	}
	public int getPeriod(ResourceModel rm,int e) throws Exception {
		if(e==0) return 0;

		int lcm=comp.computeLCM_DPRM();
		int dem=0,oldDem=0;
		int p=0,minp=-1;
		for(int t=0;t<=lcm;t++) {
			dem=(int)comp.computeDBF_DPRM(t, rm);
			//dem=(int)comp.computeDBF(t, res_p);
			//int sup=(int)rm.computeSBF(t);
			//System.out.println(t+","+dem+","+sup+","+p);
			if(oldDem==dem) continue;
			oldDem=dem;
			p=getPeriodTime(t,dem,e);
			if(minp==-1) minp=p;
			minp=Math.min(minp, p);
			//System.out.println(t+","+dem+","+p);
		}
		return minp;
	}
	public int getPeriod(int e) throws Exception {
		int lcm=comp.computeLCM_DPRM();
		int dem=0,oldDem=0;
		int p=0,minp=-1;
		for(int t=0;t<=lcm;t++) {
			dem=(int)comp.computeDBF_DPRM(t);
			if(oldDem==dem) continue;
			oldDem=dem;
			p=getPeriodTime(t,dem,e);
			if(minp==-1) minp=p;
			minp=Math.min(minp, p);
			//System.out.println(t+","+dem);
		}
		return minp;
	}

	
	public int getPeriodTime(int t,int d,int e) {
	    int max_p=0;
	    int m=(int)Math.ceil((double)(d+e)/e);
	    int c1=(int)Math.floor((double)(t+e)/m);
	    
	    int m2=m-1;
	    int c2=(int)Math.floor((double)(t+e)/m2);
	    
	    int k=(int)Math.floor((double)(t-c2+e)/c2);
	    int s=k*e+Math.max(0,t-k*c2-2*(c2-e));
	    if(s>=d)
	        max_p=c2;
	    else
	        max_p=c1;
	    return max_p;
	}
	public double getExec(int p)
	{
		int lcm=comp.computeLCM_DPRM();
		int dem=0,oldDem=0;
		double e=0,maxe=0;
		for(int t=0;t<=lcm;t++) {
			dem=comp.computeDBF_DPRM(t);
			if(oldDem==dem) continue;
			oldDem=dem;
			e=getExecTime(t,dem,p);
			maxe=Math.max(maxe, e);
			//System.out.println(t+","+dem+","+e);
		}
		return maxe;
	
	}
	public double getExecTime(int t,int d,int p) {
	    int k=(int)Math.floor((float)t/p);

	    int lim=(k+1)*p-t;

	    // case 1 : k= floor(t/p) if e>=lim
	    int kstar=k;
	    double e1=(float)(d+(kstar+2)*p-t)/(kstar+2);
	    double e2;
	    double rem_t=t-(p-e1)-kstar*p;

	    if (e1<=p-rem_t) {
	        if(kstar!=0)
	            e2=(float)d/kstar;
	        else
	            e2=d;
	    }
	    if (e1<lim) 
	        e1=p+1;
	        
	    // case 2 : k= floor(t/p) -1 if e<lim
	    kstar=k-1;
	    e2=(float)(d+(kstar+2)*p-t)/(kstar+2);
	    rem_t=t-(p-e2)-kstar*p;
	    if (e2<=p-rem_t) {
	        if(kstar!=0)
	            e2=d/kstar;
	        else
	            e2=d;
	    }
	    rem_t=t-(p-e2)-kstar*p;
	    
	    if(e2>=lim) 
	        e2=p+1;
	    
	    return Math.min(e1,e2);
	}
}
