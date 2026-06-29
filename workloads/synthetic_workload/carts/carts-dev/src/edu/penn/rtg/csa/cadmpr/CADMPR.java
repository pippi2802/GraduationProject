package edu.penn.rtg.csa.cadmpr;

import java.util.Vector;

import edu.penn.rtg.common.GlobalVariable;

/**
 * Class CacheAware DMPR.
 * It's a POJO. It uses the DMPR model structure. 
 * But the SBF of resource model is changed to effective resource SBF.
 * 
 * JDK version used: <JDK1.7>
 * @author Meng Xu
 * Create Date: 4/4/2013 
 *
 */
public class CADMPR {
	private double Pi; 		// period
	private double Theta;	// total execution time = (m-1) full VCPU's budget + 1 "partial" VCPU budget. (the partial VCPU could be full one) 
	private int m_prime;	// number of VCPU
	private int m_dedicatedCores;
	
	public CADMPR(CADMPR cadmpr){
		this.Pi = cadmpr.getPi();
		this.Theta = cadmpr.getTheta();
		this.m_prime = cadmpr.getM_prime();
		this.m_dedicatedCores = cadmpr.getM_dedicatedCores();
	}
	
	/**
	 * Function getSBF_CADMPR
	 * Return the supply bound function of the (Pi, Theta,m'). 
	 * The (Pi, Theta,m') captures the resource requirement of the partial utilization tasks
	 * The m_dedicatedCores is just used to collect the full utilization interface tasks, it's not used in the schedulability test.
	 * But it also indicate part of the resource supply of the component.
	 * In other words, the interface has two parts: (Pi,Theta,m') is for the partial utilization tasks; m_dedicatedCores is for the full utilization tasks;
	 * It can NOT use the SBF in Arvind's Journal paper in 2009 because that SBF is for McNaughton's algorithm, which is NOT applicable for hybrid EDF!
	 * We use the SBF for DMPR, i.e., MPR2hEDF in implementation. 
	 * @param t
	 * @return
	 */
	public double getSBF_CADMPR(double t, int whichApproach, Component currentComponent){
		double result = 0;
		
		if(whichApproach == GlobalVariable.TASK_CENTRIC || whichApproach == GlobalVariable.TASK_CENTRIC_UB){
			double Theta_part = this.Theta - (this.m_prime - 1)*Pi;
			double y = Math.floor( (t - (this.Pi - Theta_part)) / this.Pi);
			result = y * Theta_part + Math.max(0, t - 2*(this.Pi-Theta_part)-y*this.Pi) + (this.m_prime-1)*t;
			return result;
		}
		
		if(whichApproach == GlobalVariable.MODEL_CENTRIC){
			double Theta_part = this.Theta - (this.m_prime-1)*this.Pi;
			double N_ev23_pi = currentComponent.getNumberofVCPUPreemptionEvent(this.Pi, GlobalVariable.VCPU)
								+ currentComponent.getNumberofVCPUFinishEvent(this.Pi, GlobalVariable.VCPU);
			double delta_crpmd_max = currentComponent.getMaxCRPMDinComponent();
			double result_partialvp = 0, result_fullvps = 0;
			double Theta_star = Math.max(0, Theta_part - N_ev23_pi * delta_crpmd_max);
			double x1 = this.Pi - delta_crpmd_max - Theta_star;
			double z = this.Pi - Theta_star;
			double y1 = Math.floor((t-x1)/this.Pi);
			double x2 = N_ev23_pi * delta_crpmd_max;
			double Theta_prime = Math.max(0, this.Pi - x2);
			double y2 = Math.max(0, Math.floor((t-x2)/this.Pi));
			
			if(Theta_part != this.Pi){
				result_partialvp = y1*Theta_star + Math.max(0, t - x1 - y1*this.Pi - z);
				result_fullvps = (this.m_prime - 1)*(y2*Theta_prime + Math.max(0, t - y2*this.Pi - 2*x2));
				result = result_partialvp + result_fullvps;
				return result;
			}
			/*Consider the upper bound of the model-centric DMPR! 
			 * Suppose the interface \omega is calculated for task set
			 * which only considers higher priority task release event.
			 * The cache aware interface is upper bounded by the ceiling of \mega's bandwidth;
			 * because we will transfer a partial VCPU to a full VCPU and   */
			if(Theta_part == this.Pi){
				result_partialvp = t;
				result_fullvps = (this.m_prime - 1)*t;
				result = result_partialvp + result_fullvps;
				return result;
			}
					
		}
		System.err.println("ERROR: in getSBF_CAMPR(). Only support TASK_CENTRIC, TASK_CENTRIC_UB, AND MODEL_CENTRIC; The input whichApproach is: " +  whichApproach);
		return result;
	
	}
	
	
	
	public CADMPR() {
		
		this.Pi = -1;
		this.Theta = -1;
		this.m_prime = 0;
		this.m_dedicatedCores = 0;
	}
	
	public CADMPR(double Pi, double Theta, int m_prime) {
		this.Pi = Pi;
		this.Theta = Theta;
		this.m_prime = m_prime;
	}

	public void clear(){
		this.Theta = 0;
		this.m_prime = 0;
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
