package edu.penn.rtg.schedulingapp.basic;

public class PeriodicRM implements ResModel {
	int period;
	double exec;
	public PeriodicRM(int period, double exec) {
		this.period = period;
		this.exec = exec;
	}
	@Override
	public int getSupply(int t) {
		int y=(int) Math.floor((t-(period-exec))/period);
		double x= (int) (2*(period-exec));
		double rem=Math.max(0,t-x-y*period);
		double s=(int) (Math.floor(y*exec)+rem);
		s=Math.max(0,s);
		return (int)s;    // demand is all integer. it's ok. 
	}
	@Override
	public void display() {
		System.out.println("Res:"+period+","+exec);
		System.out.println("Bandwidth : " + (double) this.exec/(double) this.period);
		
	}
	@Override
	public double getUtil() {
		return (double)exec/period;
	}
	@Override
	public PTask getTask() {
		return new PTask(period,exec);
	}
	@Override
	public double getSupply(double t) throws Exception {
		// TODO Auto-generated method stub
		throw new Exception("call double getSupply(double) in Integer type PRM");
	}
}
