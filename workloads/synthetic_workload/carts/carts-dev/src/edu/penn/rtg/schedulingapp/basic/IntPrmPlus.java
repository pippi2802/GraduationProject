package edu.penn.rtg.schedulingapp.basic;

public class IntPrmPlus implements ResModel {
	int period;
	public double exec;
	public IntPrmPlus(int period) {
		this.period = period;
		this.exec=0;
	}
	public IntPrmPlus(int period, double exec) {
		this.period = period;
		this.exec = exec;
	}
	@Override
	public int getSupply(int t) {
		int w=(int) Math.floor(exec);
		int y=(int) Math.floor((t-(period-w))/period);
		int x=(int) (2*period-w-(Math.floor((y+1)*exec)-Math.floor(y*exec)));
		int rem=Math.max(0,t-x-y*period);
		int s=(int) (Math.floor(y*exec)+rem);
		s=Math.max(0,s);
		//System.out.println(t+","+s+","+(t-x-y*period)+","+y);
		return s;
	}
	public void display() {
		System.out.println("Res:"+period+","+exec);
		
	}
	@Override
	public double getUtil() {
		return  (double)exec/period;
	}
	@Override
	public PTask getTask() {
		// TODO Auto-generated method stub
		return null;
	}
	@Override
	public double getSupply(double t) throws Exception {
		// TODO Auto-generated method stub
		throw new Exception("use double getSupply in IntPRM");
		//return (int) getSupply((int)t);
	}
}
