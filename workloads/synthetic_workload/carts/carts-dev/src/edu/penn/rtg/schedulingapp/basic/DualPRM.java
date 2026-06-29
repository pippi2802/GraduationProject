package edu.penn.rtg.schedulingapp.basic;
// Comment 

public class DualPRM implements ResModel {
	int period1;
	double period2;
	double exec1;
	double exec2;
	
	public DualPRM(int period1,  double exec1,double period2, double exec2) {
		this.period1 = period1;
		this.period2 = period2;
		this.exec1 = exec1;
		this.exec2 = exec2;
	}

	public DualPRM(PeriodicRM res) {
		this.period1=res.period;
		this.exec1=(int) Math.floor(res.exec);
	}
	public void setMinorRes(IntPRM res) {
		// TODO Auto-generated method stub
		this.period2 = res.period;
		this.exec2 = res.exec;
	}
	public PeriodicRM getMajorRes()	{
		return new PeriodicRM(period1,exec1);
	}
	
	@Override
	public double getSupply(double t) {
		return getSupply(t,period1,exec1)+getSupply(t,period2,exec2);
	}

	private int getSupply(double t, double period, double exec) {
		if(period==0) return 0;
		int y=(int) Math.floor((t-(period-exec))/period);
		int x= (int) (2*(period-exec));
		double rem=Math.max(0,t-x-y*period);
		int s=(int) (Math.floor(y*exec)+rem);
		s=Math.max(0,s);

		return s;
	}

	public void display() {
		System.out.println("Res1:"+period1+","+exec1);
		System.out.println("Res2:"+period2+","+exec2);
		
	}

	@Override
	public double getUtil() {
		return  (double)exec1/period1+ (double)exec2/period2;
	}

	public int getPeriod1() {
		return period1;
	}

	public double getPeriod2() {
		return period2;
	}

	public double getExec1() {
		return exec1;
	}

	public double getExec2() {
		return exec2;
	}

	@Override
	public PTask getTask() {
		// TODO Auto-generated method stub
		return null;
	}

	@Override
	public int getSupply(int t) {
		// TODO Auto-generated method stub
		return (int) this.getSupply((double)t);
	}

}
