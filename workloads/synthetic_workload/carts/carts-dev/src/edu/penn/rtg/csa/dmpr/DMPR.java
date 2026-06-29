package edu.penn.rtg.csa.dmpr;

import java.util.Vector;



/**
 * Class CacheAware MPR.
 * It's a POJO. It is an interface of a component
 * DMPR has the interface <Pi, Theta, m'>, 
 *     where (Pi, Theta) is the partial VCPU in the interface; 
 *     m' is the full capacity VCPUs in the interface;
 *     the parallel level of the interface is m' if Theta =0, and (m'+1) otherwise.
 * 
 * JDK version used: <JDK1.7>
 * @author Meng Xu
 * Create Date: 4/4/2013 
 *
 */
public class DMPR {
	private double Pi; 		// period
	private double Theta;	// execution time
	private int m_prime;	// number of VCPU
	private int m_dedicatedCores;
	
	/**
	 * Function getSBF_Arvind
	 * Return the supply bound function of the (Pi, Theta,m'). 
	 * The (Pi, Theta,m') captures the resource requirement of the partial utilization tasks
	 * The m_dedicatedCores is just used to collect the full utilization interface tasks, it's not used in the schedulability test.
	 * But it also indicate part of the resource supply of the component.
	 * In other words, the interface has two parts: (Pi,Theta,m') is for the partial utilization tsks; m_dedicatedCores is for the full utilization tasks;
	 * The sbf in Arvind's Journal paper in 2009 is only for McNaughton's algorithm! It's not for hybrid EDF algorithm! 
	 * We should use our own hybrid EDF algorithm!
	 * @param t
	 * @return
	 */
	public double getSBF_Arvind(double t){
		double Theta_part = this.Theta - (this.m_prime - 1)*Pi;
		double y = Math.floor( (t - (this.Pi - Theta_part)) / this.Pi);
		double result = y * Theta_part + Math.max(0, t - 2*(this.Pi-Theta_part)-y*this.Pi) + (this.m_prime-1)*t;
		return result;//
		//TEST
//		MPR2 mpr2 = new MPR2(this.Pi,this.Theta,this.m_prime);
//		double resultMPR2 = mpr2.getSBF(t);
//		if(resultMPR2 > result+5){
//			System.out.println("MPR2 is better than DMPR! (Pi, theta, m') = (" + this.Pi + "," + this.Theta + "," + this.m_prime + ")\t t = " + t + "\t" + resultMPR2 + " > " + result);
//			mpr2.getSBF(t);
//			this.getSBF_Arvind(t);
//			System.exit(1);
//		}
		
		//return Math.floor(t/this.Pi)*this.Theta + (t - Math.floor(t/this.Pi)*this.Pi)*this.m_prime -
		//		Math.min(t - Math.floor(t/this.Pi)*Pi, this.m_prime*this.Pi - this.Theta);	
	}
	
	
	
	public DMPR() {
		
		this.Pi = -1;
		this.Theta = -1;
		this.m_prime = 0;
		this.m_dedicatedCores = 0;
	}
	
	public DMPR(double Pi, double Theta, int m_prime) {
		this.Pi = Pi;
		this.Theta = Theta;
		this.m_prime = m_prime;
		this.m_dedicatedCores = 0;
	}

	public String toString(){
		return "[" +"(" + this.Pi + "," +this.Theta + "," + this.m_prime + "), " + this.m_dedicatedCores + "]";
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



	public int getM_dedicatedCores() {
		return m_dedicatedCores;
	}



	public void setM_dedicatedCores(int m_dedicatedCores) {
		this.m_dedicatedCores = m_dedicatedCores;
	}

	
}
