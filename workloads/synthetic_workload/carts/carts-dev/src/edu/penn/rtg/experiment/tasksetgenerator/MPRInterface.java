package edu.penn.rtg.experiment.tasksetgenerator;

/**
 * Class MPRInterface
 * It's a POJO, which only store the top componennt's MPR interface. 
 * Since the overhead aware MPR interface still use the same parameter,
 * so this class can be used to analyze the top component's interface for overhead-free and overhead-aware MPR 
 * @author panda
 *
 */
public class MPRInterface {
	 
	private double Pi;
	private double Theta;
	private int m_prime;
	
	public MPRInterface(double Pi, double Theta, int m_prime){
		this.Pi = Pi;
		this.Theta = Theta;
		this.m_prime = m_prime;
	}
	
	public double getPi() {
		return Pi;
	}
	public void setPi(double pi) {
		Pi = pi;
	}
	public double getTheta() {
		return Theta;
	}
	public void setTheta(double theta) {
		Theta = theta;
	}
	public int getM_prime() {
		return m_prime;
	}
	public void setM_prime(int m_prime) {
		this.m_prime = m_prime;
	}


}
