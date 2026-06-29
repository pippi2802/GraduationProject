package edu.penn.rtg.schedulingapp.basic;

public class MultiPRM implements ResModel {
	int m;
	double period;
	double exec;
	
	public MultiPRM(int m, double period, double exec) {
		this.m = m;
		this.period = period;
		this.exec = exec;
	}

	@Override
	public double getSupply(double t) {
		double t_prime=t-(period-(int)(Math.ceil((double)exec/m)));  // ceil 
		//System.out.println(t_prime);
		if(t_prime<=0) return 0;
		double t_prime_period=(int)(Math.floor(t_prime/period));  //floor //it uses 09rtsj-virtual-clustering paper equation page8
		double x=t_prime-period*t_prime_period;
		double y=period-(int)(Math.floor(exec/m)); // floor
		int alpha=(int)(Math.floor(exec/m)); // floor 
		double beta=exec-m*alpha;
		double s=t_prime_period*exec+Math.max(0,m*x-(m*period-exec));
		if(x>=1 && x<=y) {
			return s;
		} else {
			s-=(m-beta);
			return s;
		}
	}

	@Override
	public double getUtil() {
		// TODO Auto-generated method stub
		return 0;
	}

	@Override
	public void display() {
		System.out.println(m+" "+period+" "+exec);
	}

	public int getM() {
		return m;
	}
	public double getExec() {
		return exec;
	}

	public double getLowerSupply(double t) {
		double temp=(double)exec/m;
		double temp2=t-(2*(period-temp)+2);
		double s=(double)exec/period*temp2;
		s=Math.max(0, s);
		return s;
	}

	@Override
	public PTask getTask() {
		// TODO Auto-generated method stub
		return null;
	}

	@Override
	public int getSupply(int t) throws Exception {
		// TODO Auto-generated method stub
		throw new Exception("use int getSupply(int) in MPR model with double-type Theta ");
	}

	public double getPeriod() {
		return period;
	}

	public void setPeriod(int period) {
		this.period = period;
	}

	public void setM(int m) {
		this.m = m;
	}

	public void setExec(double exec) {
		this.exec = exec;
	}

	
}
