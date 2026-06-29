package edu.penn.rtg.schedulingapp.nalgo;

import edu.penn.rtg.common.GlobalVariable;
import edu.penn.rtg.schedulingapp.basic.MultiPRM;
import edu.penn.rtg.schedulingapp.basic.ResModel;
import edu.penn.rtg.schedulingapp.basic.Workload;
import edu.penn.rtg.schedulingapp.util.Debug;

public class MultiPrmEDF implements PrmAlgo {
	Workload w;
	int period;
	boolean useLowerSBF=false;
	

	public MultiPrmEDF(Workload w, int period) {
		this.w = w;
		this.period = period;
	}

	@Override
	/*
	 * calculate the component's interface for MPR model 
	 * @see edu.penn.rtg.schedulingapp.nalgo.PrmAlgo#getRes()
	 */
	public ResModel getRes() {
		int ub=w.getUpperBoundProcessors();
		int lb=w.getLowerBoundProcessors();
		//Debug.prn(lb+","+ub);
		int m=getProcessors(lb,ub);
		//Debug.prn("xm-debug:getRes() m ="+m);
		//int m=5;
		//Debug.prn(m+","+checkExec(m,m*period));
		//Debug.prn(m+","+checkExec(m,m*period-1));
		//Debug.prn(m+","+checkExec(m,24));
		//Debug.prn(m);
		//System.exit(1);
		//m=3;
		double e=getExec(m);
		if(e==-1) 
			System.out.println("should be handled");
		//Debug.prn(m+","+e);
		Debug.prn("xm-debug:getRes() (Pi,Theta,m) "+ period+","+e+","+m);
		return new MultiPRM(m,period,e);
	}
	private int getProcessors(int lb, int ub) {
		//useLowerSBF=true;
		boolean bFound=false;
		int idx_lb=lb;
		int idx_ub=ub;
		int idx=0,old_idx=0;
		while(!bFound) {
			idx=(idx_lb+idx_ub)/2;
			if(old_idx==idx) {
				idx++;
				bFound=true;
			}
			if(checkExec(idx,idx*period-GlobalVariable.TIME_PRECISION))
				idx_ub=idx;
			else
				idx_lb=idx;
			//Debug.prn(idx_lb+","+idx_ub+","+idx);
			if(idx_lb==idx_ub) bFound=true;
			old_idx=idx;
		}
		//useLowerSBF=false;
		Debug.prn("xm: getProcessors() find the minimum number of needed processors = " + idx);
		return idx;
	}

	/*
	 * enumerate every possible e in [(m-1)*period,m*period], and return the minimum e which make the component schedulable.
	 */
	private double getExec(int m) {
		double minExec=-1;
		//only need to check e \in [(m-1)*period, m*period], because if e < (m-1)*period, (m-1) processors is enough. m is not the minimum number of processors.
		System.out.println("xm-progress: start checking every possible e in [(m-1)*period,m*period]...");
		for(double e=(m-1)*period;e<m*period;e += GlobalVariable.TIME_PRECISION) {
			if((e/GlobalVariable.TIME_PRECISION)%(1/GlobalVariable.TIME_PRECISION) == 0){
				System.out.println("xm-progress: e=" + e);
			}
			//Debug.prn(e);
			if(!checkExec(m,e))
				continue;
			if(minExec==-1)
				minExec=e;
			else if(e<minExec)
				minExec=e;
		
		}
		return minExec;
	}
	/*
	 * Check if each task can be schedulable
	 * Check if DEM(A_k + D_k) < SBF(A_k + D_k) for each k.
	 * 
	 */
	private boolean checkExec(int m,double e) {
		MultiPRM res=null;
		for(int k=0;k<w.wsize();k++) {
			res=new MultiPRM(m,period,e);
			double max_a=w.getUpperBoundArr(k,res);
			
			//Debug.prn(m+","+e+","+k+","+max_a);
			if(max_a<=0) {
				max_a=1; //xm: 1 should be a infinite number 
				//return false;
			}
			if(!checkExec(k,res,w.deadline(k),max_a))
			{
				return false;
			}
		}
		return true;
	}

	/*
	 * Check if task k is schedulable. i.e.,
	 * check if DEM(A_k+D_k) < SBF(A_k+D_k)
	 * @param k is the task index k
	 */
	private boolean checkExec(int k, MultiPRM res, int d,double max_a) {
		double sup=0;
		int dem=0;
		double a_d=0; //a_d is (A_k + D_k). it needs to check if DEM(A_k+D_k) \le sbf(A_k+D_k)
		for(double a=0;a<max_a;a += GlobalVariable.TIME_PRECISION) {
			a_d=a + w.deadline(k);
			if(useLowerSBF)
				sup=res.getLowerSupply(a_d);
			else
				sup=res.getSupply(a_d);
			dem=w.computeDEM(res.getM(), k, a_d);
			//Debug.prn(a+","+sup+","+dem);
			if(sup<dem) {
				Debug.prn("workload.get(0) interface (" + res.getPeriod() + "," + res.getExec() + "," + res.getM() + ") \t" +
						"Ak+Dk:" + (a_d) + "\t check task " + k +
						"sup: " + sup + " < dem: " + dem + "\r\n");
				return false;
			}
		}
		//Debug.prn("ok");
		return true;
		
	}
	

}
