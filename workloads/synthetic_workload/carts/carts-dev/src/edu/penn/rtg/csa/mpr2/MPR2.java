package edu.penn.rtg.csa.mpr2;

import java.util.Vector;

import edu.penn.rtg.common.GlobalVariable;

/**
 * Class MPR2.
 * It's a POJO. It is an interface of a component, which uses the MPR model proposed by Insik and Arvind
 * 
 * JDK version used: <JDK1.7>
 * @author Meng Xu
 * Create Date: 4/4/2013 
 *
 */
public class MPR2 {
	private double Pi; 		// period
	private double Theta;	// execution time
	private  int m_prime;	// number of VCPU
	
	public double getSBF_Arvind(double t){
		double t_prime = t - (Pi - Math.ceil(Theta/m_prime));
		double x = t_prime - Pi*Math.floor(t_prime/Pi);
		double y = Pi - Math.floor(Theta/m_prime);
		double beta = Theta - m_prime * Math.floor(Theta/m_prime);
		/*This is a quick fix of SBF in Arvind's paper. Don't need this fix any more because we can use getSBF_Meng() function*/
		/*if(Theta - m_prime*Pi == 0){
			return t*m_prime;
		}*/
		if(t_prime < 0){
			return 0;
		}else if(t_prime >= 0 && (x >= 1 && x<= y)){
			return Math.floor(t_prime/Pi)*Theta + Math.max(0, m_prime*x - (m_prime*Pi - Theta));
		}else if(t_prime >= 0 && (x < 1 || x > y)){
			return Math.floor(t_prime/Pi)*Theta + Math.max(0, m_prime*x - (m_prime*Pi - Theta)) - (m_prime - beta);
		}else{
			System.err.println("ERROR: CacheAwareMPR getSBF(t) is wrong! exit(1).");
			System.exit(1);
		}
		return -1;	// correct behavior won't execute this line.
	}
	
	public double getSBF_Meng(double t){
		double alpha = Math.floor( Theta * 1.0 / m_prime );
		double beta = 0;
		if(Theta - Pi * m_prime != 0){
			beta = Theta - m_prime * alpha;
		}else{
			beta = m_prime;
		}
		double y = Pi - Math.floor(Theta * 1.0 / m_prime);
		double t_prime = t - ( Pi - Math.ceil(Theta*1.0 / m_prime) );
		double x_prime = t_prime - Pi * Math.floor( t_prime * 1.0 / Pi );
		double t_double_prime = t_prime - 1;
		double x_double_prime = t_double_prime - Pi * Math.floor(t_double_prime * 1.0 / Pi) + 1;
		
		if(t_prime < 0){
			return 0;
		}else if( t_prime >= 0 && (x_prime >= 1- beta*1.0/m_prime && x_prime <= y) ){
			double result = 0;
			result = Math.floor(t_prime * 1.0 / Pi) * Theta + Math.max(0,  m_prime * x_prime - (m_prime * Pi - Theta) );
			return result;
		}else if( (t_prime >= 0 && t_prime <= 1) &&  ( x_prime < 1 - beta*1.0/m_prime || x_prime > y) ){
			double result = 0;
			result = Math.max( 0, beta*(t - 2*(Pi - Math.floor(Theta*1.0/m_prime) )) );
			return result;
		}else if( t_prime >= 1 && (x_prime < 1 - beta*1.0/m_prime || x_prime > y) ){
			double result = 0;
			result = Math.floor(t_double_prime * 1.0 / Pi) * Theta + Math.max( 0, m_prime * x_double_prime - (m_prime*Pi - Theta) - (m_prime - beta) );
			return result;
		}else{
			System.err.println("MPR2 SBF MENG's method has error! come to unexpected path! return -1");
			return -1;
		}
	}
	
	public double getSBF(double t, int sbf_type){
		if(sbf_type == GlobalVariable.MPR_SBF_ARVIND){
			return this.getSBF_Arvind(t);
		}else if(sbf_type == GlobalVariable.MPR_SBF_MENG){
			return this.getSBF_Meng(t);
		}else{
			System.err.println("MPR2 SBF no such SBF calculation method! Only support Arvind or Meng's method. return -1");
			return -1;
		}
		
	}
	
	public MPR2() {
		
		this.Pi = -1;
		this.Theta = -1;
		this.m_prime = 0;
	}
	
	public MPR2(double Pi, double Theta, int m_prime) {
		this.Pi = Pi;
		this.Theta = Theta;
		this.m_prime = m_prime;
	}

	public String toString(){
		return "(" + this.Pi + "," +this.Theta + "," + this.m_prime + ")";
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
