package edu.penn.rtg.schedulingapp.basic;

import java.util.Vector;

import edu.penn.rtg.schedulingapp.util.Debug;
import edu.penn.rtg.schedulingapp.util.MathUtil;


public class Workload {
	private Vector<PTask> tasks;
	private PeriodicRM dprm_res1=null;
	public int LCM=-1;
	
	public Workload() {
		tasks=new Vector<PTask>();
	}
	
	public void addTask(int period,double exec,int deadline)
	{
		PTask t=new PTask(period,exec,deadline);
		tasks.add(t);
	}
	public void addTask(int period,double exec)
	{
		PTask t=new PTask(period,exec);
		tasks.add(t);
	}
	public void addTask(PTask t)
	{
		// TODO Auto-generated method stub
		tasks.add(t);
	}
	public int wsize()
	{
		return tasks.size();
	}
	public int computeLCM()
	{
		LCM=MathUtil.computeLCM(tasks);
		return LCM;
	}
	public void setRes1(PeriodicRM rm) {
		dprm_res1=rm;
	}
	public double demand_EDF(int t)
	{
		double dem=0;
		for(int i=0;i<wsize();i++)
		{
			if(period(i)==0)
				continue;
			dem+=Math.floor((t+period(i)-deadline(i))/period(i))*exec(i);
		}
		//Debug.prn(dem);
		
		if(dprm_res1!=null) {   // only for DPRM
			dem-=dprm_res1.getSupply(t);
			dem=Math.max(0, dem);
		}
		
		return dem;
	}

	public int period(int i)
	{
		return tasks.elementAt(i).period;
	}
	public int deadline(int i)
	{
		return tasks.elementAt(i).deadline;
	}
	public double exec(int i)
	{
		return tasks.elementAt(i).exec;
	}
	public void display() {
		for(int i=0;i<wsize();i++)
		{
			System.out.println(period(i)+","+exec(i));
		}
		System.out.println("u:"+computeUtil());
		
	}
	public double computeUtil() {
		double util=0;
		for(int i=0;i<wsize();i++)
		{
			util+=(double)exec(i)/period(i);
		}
		return util;
	}
	private double computeUtil_not_T() {
		double util=0;
		for(int i=0;i<wsize();i++)
		{
			util+=(period(i)-deadline(i))*(double)exec(i)/period(i);
		}
		return util;
	}
	public int computeDEM(int m,int k,double t) { // t=a_k+d_k
		int dem=(int) (m*exec(k));
		for(int i=0;i<wsize();i++) {
			dem+=computeInterference_hat(k,i,t);
		}
		if(m<=1)
			return dem;
		Integer remCarryIn[]=new Integer[m-1];
		int val=0;
		remCarryIn[0]=0;
		for(int i=1;i<m-1;i++) {
			remCarryIn[i]=0;
		}
		for(int i=0;i<wsize();i++) {
			val=computeInterference_bar(k,i,t)-computeInterference_hat(k,i,t);
			//System.out.println(i+",.."+val);
			if(val>=remCarryIn[0]){
				for(int j=m-2;j>0;j--) {
					remCarryIn[j]=remCarryIn[j-1];
				}
				remCarryIn[0]=val;
			}
		}
			
		for(int i=0;i<m-1;i++) {
			dem+=remCarryIn[i];
			//System.out.println(remCarryIn[i]);
		}
		
		return dem;
	}
	private int computeW(int i, double t) {
		int t_prime=(int)Math.floor((t+period(i)-deadline(i))/period(i));
		int w=(int) (t_prime*exec(i)+carryIn(i,t));
		return w;
	}
	private int carryIn(int i,double t) {
		int t_prime=(int)Math.floor((t+period(i)-deadline(i))/period(i));
		return (int) Math.min(exec(i),Math.max(0,t-t_prime*period(i)));
		
	}
	private int computeInterference_hat(int k,int i,double t) {
		if(i!=k) {
			return (int) Math.min(computeW(i,t)-carryIn(i,t), t-exec(k));
		} else { // i==k
			return (int) Math.min(computeW(i,t)-exec(k)-carryIn(i,t), t-deadline(k)); // a_k
		}
		
	}
	private int computeInterference_bar(int k,int i,double t) {
		if(i!=k) {
			return (int) Math.min(computeW(i,t), t-exec(k));
		} else { // i==k
			return (int) Math.min(computeW(i,t)-exec(k), t-deadline(k)); // a_k
		}
		
	}
	private int exec_sum()
	{
		int sum=0;
		for(int i=0;i<wsize();i++) {
			sum+=exec(i);
		}
		return sum;
	}
	private int max_exec() {
		int max=0;
		for(int i=0;i<wsize();i++) {
			if(exec(i)>max) 
				max=(int) exec(i);
		}
		return max;
	}

	public int getUpperBoundProcessors() {
		double mindc=-1; //min(d_i - c_i)
		double val=0;
		for(int i=0;i<wsize();i++) {
			val=(double) (deadline(i)-exec(i));
			if(mindc==-1) 
				mindc=val;
			else if(val<mindc)
				mindc=val;
		}
		int num=(int)Math.ceil((double)exec_sum()/mindc);
		num+=wsize();
		return num;
	}
	public int getLowerBoundProcessors() {
		double util_t=computeUtil();
		return (int) Math.ceil(util_t);
	}

	/*
	 * It's to calculate the A_k in the schedulability test, which is Eq. 5 in Arvind's optimal cluster scheduling paper.
	 * Calculate the upper bound of A_k, which is Theorem 2 in 09rtsj-virtual-clustering
	 */
	public double getUpperBoundArr(int k,MultiPRM res) {
		double C_sum=exec_sum()-max_exec(); 
		double util_t=computeUtil();
		double util=computeUtil_not_T();
		double execperiod=(double)res.exec/res.period;
		double B=execperiod*(2+2*(res.period-(double)(res.exec)/res.m));
		double arr_upper=C_sum+res.m*exec(k)-deadline(k)*(execperiod-util_t)+util+B;
		/*
		Debug.prn(execperiod+","+util_t);
		Debug.prn(deadline(k)+","+(execperiod-util_t));
		Debug.prn(deadline(k)*(execperiod-util_t));
		Debug.prn(C_sum+res.m*exec(k)+util+B);
		Debug.prn(arr_upper);
		*/
		return Math.floor(arr_upper/(execperiod-util_t));
	}



}
