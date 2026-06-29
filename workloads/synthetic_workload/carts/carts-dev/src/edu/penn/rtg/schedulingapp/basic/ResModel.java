package edu.penn.rtg.schedulingapp.basic;

public interface ResModel {
	//meng:getSupply(int) and getSupply(double) are different functions; because two methods have the same signature if they have the same name and argument types.
	public int getSupply(int t) throws Exception;
	public double getSupply(double t) throws Exception;
	public double getUtil();
	public void display();
	public PTask getTask();
}
