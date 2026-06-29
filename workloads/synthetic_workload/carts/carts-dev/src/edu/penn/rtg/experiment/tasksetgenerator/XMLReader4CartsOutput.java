package edu.penn.rtg.experiment.tasksetgenerator;

import java.io.*;
import java.text.DecimalFormat;
import java.util.*;
import javax.xml.parsers.*;

import org.w3c.dom.*;
import org.xml.sax.SAXException;


/**
 * Class XMLReader4CartsOutput
 * This class has two functions: 
 * 1) parse the carts' output xml file to the component tree and return the tree's root.
 * 2) Parse the leaf components' vcpus paramter, create new files for gEDF, gDM, pEDF, pDM of hypervisor's scheduler;
 * 		those new files are located in the folder output/gDM/gEDF/pEDF/pDM
 * 		bin-packing algorithm used for pDM or pEDF is modified best fit algorithm
 * 			We try to avoid allocating the vcpus of same domain on the same core;
 * 			If cannot do that, allocate them on same core with least used capacity.
 * JDK version used: <JDK1.7>
 * @author Meng Xu
 * Create Date: 9/12/2013 
 *
 */

public class XMLReader4CartsOutput {
	
	private String inputFilename;
	private Document doc;
	private Vector<Vector<VCPU>> allDomUsVCPUs;
	private double system_period;	
	private int domNum;
	private Vector<CPU> cpus;
	private boolean isVCPUDistributed;
	private int coreNum;
	
	public XMLReader4CartsOutput(String inputFilename) {
		super();
		this.inputFilename = inputFilename;
		this.allDomUsVCPUs = new Vector<Vector<VCPU>>();
		this.domNum = 4;
		this.isVCPUDistributed = false;
		this.coreNum = 5;
		this.cpus = new Vector<CPU>();
		for(int i = 0; i<this.coreNum; i++){
			this.cpus.add(new CPU());
		}
	}

	public boolean parseFile(){
		try{
			doc = DocumentBuilderFactory.newInstance().newDocumentBuilder().parse(new File(inputFilename));
			Node rootNode = doc.getDocumentElement();
			if(rootNode.getAttributes().getNamedItem("name").getNodeValue().equalsIgnoreCase("system")){
				parseNode(rootNode);
			}else{
				System.err.println("The root component is not <system>");
				return false;
			}		
		}  catch (FactoryConfigurationError e) {
			System.err.println("DocumentBuilderFactory Configuration error:"+e.getMessage());
			//e.printStackTrace();
			return false;
		} catch (ParserConfigurationException e) {
			//e.printStackTrace();
			System.err.println("Parser Configuration error:"+e.getMessage());
			return false;
		} catch (SAXException e) {
			System.err.println("XML error:"+e.getMessage());
			//e.printStackTrace();
			return false;
		} catch (IOException e) {
			if( e instanceof FileNotFoundException) {
				System.err.println("Input file "+inputFilename+" is not founded");
			}
			else
			{
				System.err.println("I/O error:"+e.getMessage());
			}
			//e.printStackTrace();
			return false;
		} catch (Exception e) {
			if(e instanceof NumberFormatException) {
				System.err.println("CARTS XML tag value is not number:"+e.getMessage());
			}
			else
			{
				System.err.println("CARTS XML structure error:"+e.getMessage());
			}
			e.printStackTrace();
			return false;
		}
		
		return true;
	}
	
	private Node findNodeByName(NodeList nodes, String nodeName){
		for(int i=0; i<nodes.getLength(); i++){
			if(nodes.item(i).getNodeName().equalsIgnoreCase(nodeName)){
				return nodes.item(i);
			}
		}
		System.err.println("Node: " + nodeName + " NOT FOUND!");
		return null;
	}
	
	private Node findNodeByNameAndAttribute(NodeList nodes, String nodeName, String attribute){
		for(int i=0; i<nodes.getLength(); i++){
			if(nodes.item(i).getNodeName().equalsIgnoreCase(nodeName) && 
					nodes.item(i).getAttributes().getNamedItem("name").getNodeValue().equalsIgnoreCase(attribute)){
				return nodes.item(i);
			}
		}
		return null;
	}

	/*
	 * Function parseNode
	 * Parse each dom's vcpus and set this.allDomUsVCPUs.
	 * After calling this function, all VCPUs info. is stored in allDomUsVCPUs.
	 */
	private void parseNode(Node node){
		NodeList childNodes = node.getChildNodes();
		Node systemResourceNode = findNodeByName(childNodes, "resource");	
		Node systemModelNode = findNodeByName(systemResourceNode.getChildNodes(),"model");
		
		this.system_period = Integer.parseInt(systemModelNode.getAttributes().getNamedItem("period").getNodeValue());
		
		if(this.allDomUsVCPUs == null){
			this.allDomUsVCPUs = new Vector<Vector<VCPU>>();
		}
		for(int domIndex=0; domIndex<domNum; domIndex++){
			this.allDomUsVCPUs.add(new Vector<VCPU>());
			String currentDomName = "C" + domIndex;
			Node currentDomNode = findNodeByNameAndAttribute(childNodes,"component" ,currentDomName);
			//now parse current dom's vcpus
			Node currentDomProcessedTaskNode = findNodeByName(currentDomNode.getChildNodes(), "processed_task");
			NodeList currentDomVCPUItems = currentDomProcessedTaskNode.getChildNodes();
			for(int i= 0; i<currentDomVCPUItems.getLength(); i++){
				if(!currentDomVCPUItems.item(i).getNodeName().equalsIgnoreCase("model")){ //not all child nodes are <model period=...>,it can be "/n"
					continue;
				}
				Node currentVCPUNode = currentDomVCPUItems.item(i);
				String period = currentVCPUNode.getAttributes().getNamedItem("period").getNodeValue();
				String exe = currentVCPUNode.getAttributes().getNamedItem("execution_time").getNodeValue();
				String deadline = currentVCPUNode.getAttributes().getNamedItem("deadline").getNodeValue();
				VCPU currentVCPU = new VCPU(period, exe, deadline, domIndex);
				currentVCPU.setDomAffinity(domIndex); // set which dom it belongs to; useful later.
				this.allDomUsVCPUs.get(domIndex).add(currentVCPU);
			}
		}
	}

	/**
	 * Write all vcpus inside one component, i.e, system component, into carts' input file 
	 * @param outputFilename
	 * @param algorithm
	 */
	public void writeGlobalSchedInput(String outputFilename, String algorithm){
		String str = "";
		str += "<system os_scheduler=\"" + algorithm + "\" period=\"" + this.system_period + "\">" + "\r\n";
		for(int domIndex=0; domIndex<this.domNum; domIndex++){
			for(int vcpuIndex=0; vcpuIndex<this.allDomUsVCPUs.get(domIndex).size(); vcpuIndex++){
				VCPU vcpu = this.allDomUsVCPUs.get(domIndex).get(vcpuIndex);
				str += "<task name=\"T" +domIndex + vcpuIndex + "\" p=\"" 
						+ vcpu.getPeriod() + "\" d=\"" + vcpu.getDeadline() + "\" e=\"" 
						+ vcpu.getExe() + "\"></task> \r\n";
			}
		}
		str += "</system>\r\n";
		System.out.println(str);
		BufferedWriter outputFile;
		try {
			outputFile = new BufferedWriter(new FileWriter(outputFilename));
			outputFile.write(str);
			outputFile.close();
		} catch (IOException e) {
			// TODO Auto-generated catch block
			e.printStackTrace();
		}
		
	}
	
	private boolean isFeasible(VCPU vcpu, CPU core){
		double vcpu_util = vcpu.getExe()*1.0/vcpu.getPeriod();
		
		if(vcpu_util + core.getUsed_capacity() <= 1 &&
				!core.hasDomiOnIt(vcpu.getDomAffinity())){//is Feasible
			return true;
		}else{
			return false;
		}
	}
	
	private void setVCPU2Core(VCPU vcpu, CPU core){
		double newUsedCapacity = core.getUsed_capacity() + vcpu.getExe()*1.0/vcpu.getPeriod();
		core.setUsed_capacity(newUsedCapacity);
		core.setDomiOnIt(vcpu.getDomAffinity());
		core.getVcpus().add(vcpu);
	}
	/**
	 * When a vcpu cannot find a feasible core, either because of total util < 1 or 
	 * more than 2 vcpus of the dom allocated to same core.
	 * First avoid allocating 2 vcpus of same dom to the same core and place the vcpu to a core with least used capacity
	 * If all cores have a vcpu of this dom, just find a core with least used capacity
	 * @param vcpu
	 * @param cpus
	 */
	private void forceAllocateCore2VCPU(VCPU vcpu, Vector<CPU> cpus){
		double bestUsedCapacity = 100000; 
		int bestCoreIndex = -1;
		for(int coreIndex=0; coreIndex<cpus.size(); coreIndex++ ){
			CPU currentCore = cpus.get(coreIndex);
			if(!currentCore.hasDomiOnIt(vcpu.getDomAffinity())){
				if(currentCore.getUsed_capacity() < bestUsedCapacity ){
					bestUsedCapacity = currentCore.getUsed_capacity();
					bestCoreIndex = coreIndex; 
				}
			}
		}
		//cannot find a core that no two vcpus of same domain run on it. bestUsedCapacity and bestCoreIndex has never updated.
		//remove the constrain of no two vcpu of same dom and try again
		if(bestCoreIndex == -1){	
			for(int coreIndex=0; coreIndex<cpus.size(); coreIndex++){
				CPU currentCore = cpus.get(coreIndex);
				if(currentCore.getUsed_capacity() < bestUsedCapacity ){
					bestUsedCapacity = currentCore.getUsed_capacity();
					bestCoreIndex = coreIndex; 
				}
			}
		}
		if(bestCoreIndex != -1){ 
			setVCPU2Core(vcpu, cpus.get(bestCoreIndex));
		}else{
			System.err.println("Try every effort and cannot allocate a core for this vcpu. Fail. Check bestUsedCapacity's value(> 100000); Exit(1)");
			System.exit(1);
		}
	}
	
	private void distributeVCPUs2Cores(String partitionAlgorithm){
		if(!partitionAlgorithm.equalsIgnoreCase("BEST-FIT")){
			System.err.println("Only support Best-Fit now. exit(1)");
			System.exit(1);
		}
		
		for(int domIndex=0; domIndex < this.allDomUsVCPUs.size(); domIndex++){
			Vector<VCPU> vcpus = this.allDomUsVCPUs.get(domIndex);
			for(int vcpuIndex=0; vcpuIndex < vcpus.size(); vcpuIndex++){
				VCPU currentVCPU = vcpus.get(vcpuIndex);
				//Best-Fit algorithm //The Best Fit algorithm places a new object in the fullest bin that still has room. //http://www.cs.arizona.edu/icon/oddsends/bpack/bpack.htm
				double bestRemainCapacity = 1;
				int bestCoreIndex = -1;
				for(int coreIndex=0; coreIndex<this.coreNum; coreIndex++){
					CPU currentCore = this.cpus.get(coreIndex);
					if(isFeasible(currentVCPU, currentCore)){//check if a core is feasible for this vcpu
						double currentRemainCapacity = 1 - (currentCore.getUsed_capacity() + currentVCPU.getExe()*1.0/currentVCPU.getPeriod());
						if(currentRemainCapacity < bestRemainCapacity){ //the core is current best core
							bestRemainCapacity = currentRemainCapacity;
							bestCoreIndex = coreIndex;
						}
					}	
				}
				if(bestCoreIndex != -1){ //this vcpu find a feasible core
					setVCPU2Core(currentVCPU, this.cpus.get(bestCoreIndex));
				}else{ //this vcpu cannot find a feasible core; force allocating a core to this vcpu
					forceAllocateCore2VCPU(currentVCPU, this.cpus);
				}
			}
		}
		
	}
	
	/**
	 * call distributeVPUS() to distribute vcpus to each core
	 * write each core's vcpus as task in a component
	 * these components are under system top component 
	 * @param outputFilename
	 * @param algorithm
	 */
	public void writePartitionSchedInput(String outputFilename, String algorithm){
		if(isVCPUDistributed == false){
			distributeVCPUs2Cores("Best-Fit");
		}
		String str = "";
		str += "<system os_scheduler=\"" + algorithm + "\" period=\"" + this.system_period + "\">" + "\r\n";
		for(int coreIndex = 0; coreIndex < this.coreNum; coreIndex++){
			CPU currentCore = this.cpus.get(coreIndex);
			str += "<component name=\"core" + coreIndex + "\" scheduler=\"" + algorithm 
					+ "\" period=\"" + this.system_period + "\"> \r\n"; 
	
			Vector<VCPU> currentVCPUs = currentCore.getVcpus();
			for(int i=0; i<currentVCPUs.size(); i++){
				VCPU vcpu = currentVCPUs.get(i);
				str += "<task name=\"T" + vcpu.getDomAffinity() + i + "\" p=\"" 
						+ vcpu.getPeriod() + "\" d=\"" + vcpu.getDeadline() + "\" e=\"" 
						+ vcpu.getExe() + "\"></task> \r\n";
			}
			
			str += "</component> \r\n";
		}
		
		str += "</system>\r\n";
		System.out.println(str);
		BufferedWriter outputFile;
		try {
			outputFile = new BufferedWriter(new FileWriter(outputFilename));
			outputFile.write(str);
			outputFile.close();
		} catch (IOException e) {
			// TODO Auto-generated catch block
			e.printStackTrace();
		}
		
	}
	
	
	/**
	 * Write a range of taskset's domU's vcpus into carts input file
	 * Call writeGlobalSchedInput(String outputFilename, String algorithm) to write each file
	 * Works for gEDF and gDM
	 * @param util_start
	 * @param util_step
	 * @param util_end
	 * @param tasksetNum
	 * @param subPath, default is input
	 */
	public static void writeBatchOfSchedInput(double util_start, double util_step,
			double util_end,int tasksetNum){
		DecimalFormat df = new DecimalFormat("#.##");
		df.setMinimumFractionDigits(2);
		df.setMaximumFractionDigits(2);
		String algorithms[] = {"gEDF","gDM", "pEDF", "pDM"};
		for(int i=0; i<algorithms.length; i++){
			String algorithm = algorithms[i];
			String topPath = df.format(util_start) + "-"+ df.format(util_step) + "-" + df.format(util_end)
					+ "-" + tasksetNum;
			for(double util= util_start; util<util_end; util+=util_step){
				String wholeInputFolderPath = topPath + "/" + "input" + "/" + df.format(util);
				String wholeOutputFolderPath = topPath + "/" + "output/" + algorithm;
				boolean isFolderCreated = (new File(wholeOutputFolderPath)).mkdirs();
				if(!isFolderCreated){System.err.println("Create the folder " + wholeOutputFolderPath + " files fails!");}
				wholeOutputFolderPath += "/"+ df.format(util);
				isFolderCreated = (new File(wholeOutputFolderPath)).mkdirs();
				if(!isFolderCreated){System.err.println("Create the folder " + wholeOutputFolderPath + " files fails!");}
				
				for(int tasksetIndex=0; tasksetIndex < tasksetNum; tasksetIndex++){
					String inputFilename = wholeInputFolderPath + "/" + tasksetIndex + "-" + df.format(util) + "-MPR2-out.xml";
					String outputFilename = wholeOutputFolderPath + "/" + tasksetIndex + "-" + df.format(util) + "-" + algorithm + "-vmm-in.xml";
					XMLReader4CartsOutput reader = new XMLReader4CartsOutput(inputFilename);
					reader.parseFile();
					if(algorithm.equalsIgnoreCase("gEDF") || algorithm.equalsIgnoreCase("gDM")){
						reader.writeGlobalSchedInput(outputFilename, algorithm);
					}else if(algorithm.equalsIgnoreCase("pEDF") || algorithm.equalsIgnoreCase("pDM")){
						reader.writePartitionSchedInput(outputFilename, algorithm);
					}
					
				}
				
			}
		}
	}

	/**
	 * @param args
	 */
	public static void main(String[] args) {
		// TODO Auto-generated method stub
		if(args.length < 1){
			printUsage();
			System.exit(0);
		}
		
		double util_start = Double.parseDouble(args[0]);
		double util_step = Double.parseDouble(args[1]);
		double util_end = Double.parseDouble(args[2]);
		int tasksetNum = Integer.parseInt(args[3]);
		XMLReader4CartsOutput.writeBatchOfSchedInput(util_start,util_step, util_end, tasksetNum); //passed the test

	}
	
	public static void printUsage(){
		System.out.println("[Usage] XMLReader4CartsOutput util(start step end) tasksetNum");
	}

	
	//////////Get and Set Method///////////////////////////


	public String getInputFilename() {
		return inputFilename;
	}






	public void setInputFilename(String inputFilename) {
		this.inputFilename = inputFilename;
	}



	public Document getDoc() {
		return doc;
	}


	public void setDoc(Document doc) {
		this.doc = doc;
	}

	public Vector<Vector<VCPU>> getAllDomUsVCPUs() {
		return allDomUsVCPUs;
	}

	public void setAllDomUsVCPUs(Vector<Vector<VCPU>> allDomUsVCPUs) {
		this.allDomUsVCPUs = allDomUsVCPUs;
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
	
	

}
