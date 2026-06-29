package edu.penn.rtg.experiment.tasksetgenerator;

import java.io.*;
import java.text.DecimalFormat;
import java.util.*;
import javax.xml.parsers.*;

import org.w3c.dom.*;
import org.xml.sax.SAXException;

/** 
 * This class is only for rtas14 paper. Make guest domain's gEDF to pEDF and pDM.
 * Parse the gEDF guest domain's tasks, and distribute them to different VCPUs, set different scheduler for it.
 */

public class TransferGuestDomTo4AlgNonHarmonic {
	
	private String inputFilename;
	private String outputFilename;
	private Document doc;
	private double system_period;	
	private int domNum;
	private Vector<Domain> doms;
	private String alg;

	/**
	 * @param args
	 */
	public static void main(String[] args) {
		// TODO Auto-generated method stub
		
		if(args.length == 1){
			System.out.println("test program");
			String inputFileName = "./0-3.50.txt";
			String outputFileName = "0-3.50-pEDF-in.xml";
			TransferGuestDomTo4AlgNonHarmonic transferObj = new TransferGuestDomTo4AlgNonHarmonic(inputFileName, outputFileName);
			transferObj.setAlg("pEDF");
			transferObj.transfer();
			System.exit(0);
		}
		
		String inputRootDir = "./data/sched";
		String outputRootDir = "./data/sched_nonharmonic";
		String dists[] = {"heavy-bimodal", "heavy-uniform", "medium-bimodal", "medium-uniform", "light-bimodal", "light-uniform"};
		double util_min = 0.90;
		double util_step = 0.20;
		double util_max = 5.00;
		double taskset_num = 25;
		DecimalFormat df = new DecimalFormat("#.##");
		df.setMinimumFractionDigits(2);
		df.setMaximumFractionDigits(2);
		String algs[] = {"pEDF", "pDM", "gEDF", "gDM"};
		for(int i=0; i<dists.length; i++){
			String inputDir = inputRootDir + "/" + dists[i] + "/" + "input";
			String outputDir = outputRootDir + "/" + dists[i] + "/" + "input";
 			for(double util = util_min; util < util_max; util+=util_step){
				for(int index=0; index < taskset_num; index++){
					String inputFileName = inputDir + "/" + df.format(util) + "/" + index + "-" + df.format(util) + ".txt";
					String outputUtilFolderName =  outputDir + "/" + df.format(util);
					File outputUtilFolder = new File(outputUtilFolderName);
					outputUtilFolder.mkdirs();
					for(int algIndex =0; algIndex < algs.length; algIndex++ ){
						String outputFileName = outputDir + "/" + df.format(util) + "/" + index + "-" + df.format(util) + "-" +algs[algIndex] + "-nonharmonic-in.xml";	
						TransferGuestDomTo4AlgNonHarmonic transferObj = new TransferGuestDomTo4AlgNonHarmonic(inputFileName, outputFileName);
						transferObj.setAlg(algs[algIndex]);
						transferObj.transfer();
						System.out.println("finish transfer domU's alg to 4 alg. Note: use pDM's Utilizatin Bound for parititon");
					}
					
				} 
			}
		}
	}
	
	
	public TransferGuestDomTo4AlgNonHarmonic(String inputFilename, String outputFilename) {
		super();
		this.inputFilename = inputFilename;
		this.outputFilename = outputFilename;
		this.domNum = 4;
		this.doms = new Vector<Domain>();
		for(int i=0; i<this.domNum; i++){
			this.doms.add(new Domain());
		}
		this.doms.get(0).setPeriod("226");
		this.doms.get(1).setPeriod("250");
		this.doms.get(2).setPeriod("84");
		this.doms.get(3).setPeriod("125");
	}
	
	public void transfer(){
		readTaskset(this.inputFilename); //set this.doms.taskset;
		distributeTasks("best-fit"); //distribute each domain's tasks to several vcpus.
		writeResult2File(this.outputFilename);
		
	}
	
	public void readTaskset(String inputFileName){
		try{
			BufferedReader inputFile = new BufferedReader(new FileReader(inputFileName));
			String line = "";
			line = inputFile.readLine(); //first line is description
			if( !(line.split("\t")[1].equalsIgnoreCase(" period"))){
				System.err.println(line + "split result is incorrect! split[1] is not period");
				System.err.println("split[1] is " + line.split("\t")[1]);
				System.exit(1);
			}
			int domIndex = 0;
			while( (line = inputFile.readLine()) != null){
				String[] fields = line.split("\t");
			  //System.out.println("fields length = " + fields.length + " fields[3] = " + fields[3]);
				//0:name; 1:period; 2:exe; 3:ddl.(delta_rel); 4:delta_sch; 5:delta_cxs; 6:delta_crpmd
				String deadline = fields[3].substring(0,5); //txt file has problem: deadline and delta_rel are concated
				if(Double.parseDouble(deadline) != Double.parseDouble(fields[1])){
					System.err.println("parse task.input file fails. ddl != period");
					System.exit(1);
				}
				Task task = new Task(fields[1], fields[2], deadline, fields[6], fields[0]);
				this.doms.get(domIndex).getTaskset().add(task);
				domIndex = (++domIndex)%this.domNum;
			}
			
		}catch (Exception e){
			e.printStackTrace();
		}
	}
	
	public boolean getIsFeasibleOnThisVCPU(VCPU currentVCPU, Task currentTask){
		if(this.alg.equalsIgnoreCase("pEDF")){ //utilization bound is 1
			if(currentVCPU.getUsedUtil() + currentTask.getExe()*1.0/currentTask.getPeriod() <= 1)
				return true;
			else 
				return false;
		}else if(this.alg.equalsIgnoreCase("pDM")){
			double currentTotalUtil = currentVCPU.getUsedUtil() + currentTask.getExe()*1.0/currentTask.getPeriod();
			int taskTotalNum = currentVCPU.getTaskset().size() + 1; //the number of tasks after packing
			double utilizationBound = taskTotalNum * (Math.pow(2, 1.0/taskTotalNum) - 1);
			if(currentTotalUtil <= utilizationBound)
				return true;
			else
				return false;	
		}else{
			System.err.println("only support pEDF/pDM in getIsFeasibleOnThisVCPU()");
			System.exit(1);
		}
		return true; //cannot reach
	}
	
	public void distributeTasks(String binPack){
		if(!binPack.equalsIgnoreCase("best-fit")){
			System.err.println("Only support best fit");
			System.exit(1);
		}
		if(this.alg.equalsIgnoreCase("gEDF") || this.alg.equalsIgnoreCase("gDM")){
			return;
		}
		for(int domIndex=0; domIndex<this.domNum; domIndex++){
			Domain currentDom = this.doms.get(domIndex);
			Vector<Task> taskset = this.doms.get(domIndex).getTaskset();
			for(int taskIndex=0; taskIndex < taskset.size(); taskIndex++){
				Task currentTask = taskset.get(taskIndex);
			
				double bestRemainUtil = 10;
				int bestVCPUIndex = -1;
				//find best vcpu to place the task onto
				for(int vcpuIndex =0; vcpuIndex < currentDom.getVCPUs().size(); vcpuIndex++){
					VCPU currentVCPU = currentDom.getVCPUs().get(vcpuIndex);
					boolean isFeasibleOnThisVCPU = this.getIsFeasibleOnThisVCPU(currentVCPU, currentTask);
					double currentRemainUtil = 1 - (currentVCPU.getUsedUtil() + currentTask.getExe()*1.0/currentTask.getPeriod());
					if(isFeasibleOnThisVCPU == true && currentRemainUtil < bestRemainUtil){
						bestRemainUtil = currentRemainUtil;
						bestVCPUIndex = vcpuIndex;
					}
				}
				//place the taskset to the best vcpu
				if(bestVCPUIndex != -1){
					currentDom.getVCPUs().get(bestVCPUIndex).getTaskset().add(currentTask);
					double usedUtil = currentDom.getVCPUs().get(bestVCPUIndex).getUsedUtil() 
									+ currentTask.getExe()*1.0/currentTask.getPeriod();
					currentDom.getVCPUs().get(bestVCPUIndex).setUsedUtil(usedUtil);
				}else{//need more vcpus
					VCPU newVCPU = new VCPU(0);
					newVCPU.getTaskset().add(currentTask);
					newVCPU.setUsedUtil(currentTask.getExe()*1.0/currentTask.getPeriod());
					currentDom.getVCPUs().add(newVCPU);
				}
				
			
			}
		}
		
	}
	
	
	/*
	 * write each domain's vcpu to a file
	 */
	public void writeResult2File(String outputFileName){
		String str = "";
		if(this.alg.equalsIgnoreCase("pEDF") || this.alg.equalsIgnoreCase("pDM")){
			str += "<system os_scheduler=\"" + this.alg + "\" period=\"" + "16.0\">\r\n";
			for(int domIndex=0; domIndex<this.domNum; domIndex++){
				Domain curDomain = this.getDoms().get(domIndex);
				str += "\t<component name=\"C" + domIndex + "\" scheduler=\"" + this.alg + "\" period=\"" + curDomain.getPeriod() + "\">\r\n";
				for(int vcpuIndex=0; vcpuIndex<curDomain.getVCPUs().size();vcpuIndex++){
					VCPU curVCPU = curDomain.getVCPUs().get(vcpuIndex);
					str += "\t\t<component name=\"C"+domIndex + "VP" + vcpuIndex + "\" scheduler=\"" + this.alg + "\" period=\"" + curDomain.getPeriod() + "\">\r\n";
					for(int taskIndex=0; taskIndex < curVCPU.getTaskset().size();taskIndex++){
						Task curTask = curVCPU.getTaskset().get(taskIndex);
						str += "\t\t\t<task name=\"" + curTask.getName() + "\" p=\"" + curTask.getPeriod() + "\" d=\"" + curTask.getDeadline() + "\" e=\"" +
								curTask.getExe() + "\" delta_rel=\"0\" delta_sch=\"0\" delta_cxs=\"0\" delta_crpmd=\"0.09\"></task> \r\n";
					}
					
					str += "\t\t</component>\r\n"; //vcpu component ends
				}
				
				str += "\t</component>\r\n";
			}
			
			str +=  "</system>\r\n";
				
		}else if(this.alg.equalsIgnoreCase("gEDF") || this.alg.equalsIgnoreCase("gDM")){
			str += "<system os_scheduler=\"" + this.alg + "\" period=\"" + "16.0\">\r\n";
			for(int domIndex = 0; domIndex < this.domNum; domIndex++){
				Domain curDomain = this.getDoms().get(domIndex);
				str += "\t<component name=\"C" + domIndex + "\" scheduler=\"" + this.alg + "\" period=\"" + curDomain.getPeriod() + "\">\r\n";
				Vector<Task> taskset = this.getDoms().get(domIndex).getTaskset();
				for(int taskIndex=0; taskIndex < taskset.size(); taskIndex++){
					Task curTask = taskset.get(taskIndex);
					str += "\t\t\t<task name=\"" + curTask.getName() + "\" p=\"" + curTask.getPeriod() + "\" d=\"" + curTask.getDeadline() + "\" e=\"" +
							curTask.getExe() + "\" delta_rel=\"0\" delta_sch=\"0\" delta_cxs=\"0\" delta_crpmd=\"0.09\"></task> \r\n";
				}
				
				str += "\t</component>\r\n";
			}			
			str += "</system>\r\n";
		}else{
			System.err.println("Error: no such algorithm: " + this.alg);
			System.exit(1);
		}
		try{
			BufferedWriter outputFile = new BufferedWriter(new FileWriter(outputFileName));
			outputFile.write(str);
			outputFile.close();
			//System.out.println(str);
		}catch(Exception e){
			e.printStackTrace();
		}
		
	}
	
	
	
	
	public String getInputFilename() {
		return inputFilename;
	}


	public void setInputFilename(String inputFilename) {
		this.inputFilename = inputFilename;
	}


	public String getOutputFilename() {
		return outputFilename;
	}


	public void setOutputFilename(String outputFilename) {
		this.outputFilename = outputFilename;
	}


	public Document getDoc() {
		return doc;
	}


	public void setDoc(Document doc) {
		this.doc = doc;
	}


	public double getSystem_period() {
		return system_period;
	}


	public void setSystem_period(double system_period) {
		this.system_period = system_period;
	}


	public int getDomNum() {
		return domNum;
	}


	public void setDomNum(int domNum) {
		this.domNum = domNum;
	}


	public Vector<Domain> getDoms() {
		return doms;
	}


	public void setDoms(Vector<Domain> doms) {
		this.doms = doms;
	}


	public String getAlg() {
		return alg;
	}


	public void setAlg(String alg) {
		this.alg = alg;
	}

	
	

}
